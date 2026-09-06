"""Carga do star schema (gold em parquet) no warehouse SQL Server, partição a partição.

Uso: `uv run carga-dw` (container local) ou `uv run carga-dw --env .env.nuvem` (um destino
externo, por `DW_URL`). Cria o banco e o schema `dw` se não existirem; dimensões são
recriadas por inteiro (são pequenas); fatos são tabelas com índice columnstore clusterizado,
carregadas por partição de ano (`DW_ANOS` seleciona) com apagar-e-inserir, o que torna a
carga idempotente por partição. Ao final, presta contas: linhas do parquet × linhas na tabela.
"""

from __future__ import annotations

import argparse
import re
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pyodbc
from dotenv import load_dotenv

from interiores_fictoria import db
from interiores_fictoria.config import RAIZ_PROJETO, anos_carga_dw, conexao_warehouse
from interiores_fictoria.gold import modelo
from interiores_fictoria.lake import Lake, abrir_lake, novo_manifesto

SCHEMA = "dw"


def _tipo_sql(campo: pa.Field, tabela: pa.Table) -> str:
    t = campo.type
    if pa.types.is_int64(t) or pa.types.is_uint64(t):
        return "bigint"
    if pa.types.is_int32(t) or pa.types.is_uint32(t):
        return "int"
    if pa.types.is_int16(t) or pa.types.is_int8(t) or pa.types.is_uint16(t) or pa.types.is_uint8(t):
        return "smallint"
    if pa.types.is_boolean(t):
        return "bit"
    if pa.types.is_decimal(t):
        return f"decimal({min(t.precision, 38)},{t.scale})"
    if pa.types.is_floating(t):
        return "float"
    if pa.types.is_timestamp(t):
        return "datetime2(0)"
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        col = tabela.column(campo.name)
        maior = pc.max(pc.utf8_length(col)).as_py() if tabela.num_rows else None
        n = max(50, int(maior or 0) * 2)
        return f"varchar({min(n, 4000)})"
    raise ValueError(f"tipo Arrow sem mapeamento para SQL Server: {t} ({campo.name})")


def _ddl(nome: str, tabela: pa.Table, extra: str = "") -> str:
    cols = ", ".join(f"[{c.name}] {_tipo_sql(c, tabela)} NULL" for c in tabela.schema)
    return f"CREATE TABLE {SCHEMA}.{nome} ({cols}{extra})"


def _linhas(tabela: pa.Table) -> list[tuple[Any, ...]]:
    colunas = [c.to_pylist() for c in tabela.columns]
    return [
        tuple(float(v) if isinstance(v, Decimal) else v for v in linha)
        for linha in zip(*colunas, strict=True)
    ]


def _inserir(
    conn: pyodbc.Connection, nome: str, tabela: pa.Table, extra_cols: dict[str, Any] | None = None
) -> int:
    if tabela.num_rows == 0:
        return 0
    nomes = list(tabela.schema.names) + list((extra_cols or {}).keys())
    marcadores = ", ".join("?" for _ in nomes)
    cols = ", ".join(f"[{c}]" for c in nomes)
    linhas = _linhas(tabela)
    if extra_cols:
        extra = tuple(extra_cols.values())
        linhas = [(*linha, *extra) for linha in linhas]
    cur = conn.cursor()
    cur.fast_executemany = True
    try:
        for i in range(0, len(linhas), 20_000):
            cur.executemany(
                f"INSERT INTO {SCHEMA}.{nome} ({cols}) VALUES ({marcadores})",
                linhas[i : i + 20_000],
            )
        conn.commit()
    finally:
        cur.close()
    return len(linhas)


def _conexao_master(conexao: str) -> str:
    return re.sub(r"Database=[^;]+", "Database=master", conexao)


def preparar_banco(conexao: str) -> None:
    banco = re.search(r"Database=([^;]+)", conexao)
    nome = banco.group(1) if banco else "dw_fictoria"
    master = db.conectar(_conexao_master(conexao), autocommit=True)
    try:
        db.executar(
            master,
            f"IF DB_ID(N'{nome}') IS NULL CREATE DATABASE [{nome}] COLLATE Latin1_General_100_CI_AI_SC_UTF8",
        )
    finally:
        master.close()
    conn = db.conectar(conexao)
    try:
        db.executar(conn, f"IF SCHEMA_ID('{SCHEMA}') IS NULL EXEC('CREATE SCHEMA {SCHEMA}')")
        conn.commit()
    finally:
        conn.close()


def carregar_dimensao(conn: pyodbc.Connection, lake: Lake, nome: str) -> int:
    tabela = lake.ler_parquet("gold", nome, "parte-000.parquet")
    db.executar(
        conn, f"IF OBJECT_ID('{SCHEMA}.{nome}', 'U') IS NOT NULL DROP TABLE {SCHEMA}.{nome}"
    )
    db.executar(conn, _ddl(nome, tabela))
    chave = tabela.schema.names[0]
    if chave.startswith("sk_") and len(pc.unique(tabela.column(chave))) == tabela.num_rows:
        db.executar(
            conn,
            f"ALTER TABLE {SCHEMA}.{nome} ALTER COLUMN [{chave}] {_tipo_sql(tabela.schema.field(chave), tabela)} NOT NULL",
        )
        db.executar(
            conn,
            f"ALTER TABLE {SCHEMA}.{nome} ADD CONSTRAINT pk_{nome} PRIMARY KEY CLUSTERED ([{chave}])",
        )
    conn.commit()
    return _inserir(conn, nome, tabela)


def carregar_fato(
    conn: pyodbc.Connection, lake: Lake, nome: str, anos: list[int] | None
) -> dict[int, dict[str, int]]:
    particoes = sorted(p for p in lake.listar("gold", nome) if "ano=" in p)
    resultado: dict[int, dict[str, int]] = {}
    for pasta in particoes:
        ano = int(pasta.rsplit("ano=", 1)[1].strip("/"))
        if anos and ano not in anos:
            continue
        arquivo = f"{pasta}/parte-000.parquet"
        with lake.fs.open(arquivo, "rb") as f:
            tabela = pq.read_table(f)
        if not db.escalar(conn, f"SELECT OBJECT_ID('{SCHEMA}.{nome}', 'U')"):
            db.executar(conn, _ddl(nome, tabela, ", [ano] int NOT NULL"))
            db.executar(conn, f"CREATE CLUSTERED COLUMNSTORE INDEX cci_{nome} ON {SCHEMA}.{nome}")
            conn.commit()
        db.executar(conn, f"DELETE FROM {SCHEMA}.{nome} WHERE ano = ?", ano)
        conn.commit()
        inseridas = _inserir(conn, nome, tabela, {"ano": ano})
        na_tabela = int(
            db.escalar(conn, f"SELECT COUNT(*) FROM {SCHEMA}.{nome} WHERE ano = ?", ano) or 0
        )
        resultado[ano] = {"parquet": tabela.num_rows, "inseridas": inseridas, "tabela": na_tabela}
    return resultado


def main() -> None:
    p = argparse.ArgumentParser(description="Carga do star schema da gold no warehouse SQL Server.")
    p.add_argument(
        "--env", help="arquivo .env alternativo (ex.: .env.nuvem) com DW_URL/DW_* do destino"
    )
    args = p.parse_args()
    if args.env:
        load_dotenv(
            Path(args.env) if Path(args.env).is_absolute() else RAIZ_PROJETO / args.env,
            override=True,
        )
    conexao = conexao_warehouse()
    anos = anos_carga_dw()
    lake = abrir_lake()
    manifesto = novo_manifesto("warehouse")
    inicio = time.perf_counter()
    preparar_banco(conexao)
    conn = db.conectar(conexao)
    falhas: list[str] = []
    try:
        print(
            f"Warehouse: gold → SQL Server ({'todos os anos' if not anos else 'anos ' + ', '.join(map(str, anos))})\n"
        )
        print(f"  {'dimensão':24} {'linhas':>9} {'tempo':>7}")
        for nome in modelo.DIMENSOES:
            t0 = time.perf_counter()
            n = carregar_dimensao(conn, lake, nome)
            manifesto.registrar(nome, tipo="dimensao", linhas=n)
            print(f"  {nome:24} {n:>9} {time.perf_counter() - t0:>6.1f}s")
        print(f"\n  {'fato':24} {'ano':>5} {'parquet':>9} {'tabela':>9} {'tempo':>7}")
        for nome in modelo.FATOS:
            t0 = time.perf_counter()
            r = carregar_fato(conn, lake, nome, anos)
            manifesto.registrar(nome, tipo="fato", por_ano=r)
            for ano, d in r.items():
                ok = d["parquet"] == d["tabela"]
                if not ok:
                    falhas.append(f"{nome} {ano}")
                print(
                    f"  {nome:24} {ano:>5} {d['parquet']:>9} {d['tabela']:>9} {'' if ok else '  DIVERGE'}"
                )
            print(f"  {'':24} {'':>5} {'':>9} {'':>9} {time.perf_counter() - t0:>6.1f}s")
        tamanho = db.escalar(
            conn,
            "SELECT CAST(SUM(a.total_pages) * 8.0 / 1024 AS decimal(10,1)) FROM sys.allocation_units a "
            "JOIN sys.partitions p ON p.hobt_id = a.container_id OR p.partition_id = a.container_id "
            "JOIN sys.objects o ON o.object_id = p.object_id WHERE o.schema_id = SCHEMA_ID('dw')",
        )
    finally:
        conn.close()
    dados = manifesto.fechar()
    dados["falhas"] = falhas
    lake.escrever_json(dados, "gold", "_controle", f"carga_dw_{manifesto.execucao}.json")
    print(
        f"\nConcluído em {time.perf_counter() - inicio:.1f}s. Tamanho do schema dw: {tamanho} MB."
    )
    if falhas:
        raise SystemExit("Prestação de contas FALHOU em: " + ", ".join(falhas))
    print(
        "Prestação de contas: todas as partições batem com o parquet. Próximo: uv run notebooks-modelo"
    )


if __name__ == "__main__":
    main()
