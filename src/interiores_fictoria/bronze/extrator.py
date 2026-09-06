"""Bronze: extração do staging para parquet, uma pasta por carga, com esquema explícito.

Uso: `uv run bronze-staging`. Para cada uma das 30 tabelas do staging, lê as linhas com
`_rv_origem` maior que a marca do bronze (a primeira execução traz tudo), grava em
`bronze/<schema>.<tabela>/carga=<execucao>/parte-000.parquet` e confere a contagem
lida contra a escrita. O bronze é append-only e intocável: cada carga é uma pasta nova,
e o estado corrente por chave é responsabilidade da silver (maior `_rv_origem` vence).
O esquema Arrow vem do INFORMATION_SCHEMA, não da inferência: tipos estáveis entre cargas.
"""

from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pyodbc

from interiores_fictoria import db
from interiores_fictoria.config import conexao_staging
from interiores_fictoria.lake import Lake, abrir_lake, novo_manifesto
from interiores_fictoria.staging.carga_incremental import TABELAS

CONTROLE = "bronze/_controle"


def tipo_arrow(tipo_sql: str, precisao: int | None, escala: int | None) -> pa.DataType:
    t = tipo_sql.lower()
    if t == "bigint":
        return pa.int64()
    if t == "int":
        return pa.int32()
    if t in ("smallint", "tinyint"):
        return pa.int16()
    if t == "bit":
        return pa.bool_()
    if t in ("decimal", "numeric"):
        return pa.decimal128(precisao or 18, escala or 0)
    if t in ("datetime2", "datetime", "smalldatetime"):
        return pa.timestamp("us")
    if t == "date":
        return pa.date32()
    if t in ("varchar", "nvarchar", "char", "nchar", "text"):
        return pa.string()
    if t in ("binary", "varbinary", "timestamp"):
        return pa.binary()
    if t in ("float", "real"):
        return pa.float64()
    raise ValueError(f"tipo SQL sem mapeamento para Arrow: {tipo_sql}")


def esquema_da_tabela(conn: pyodbc.Connection, tabela: str) -> pa.Schema:
    schema, nome = tabela.split(".")
    colunas = db.consultar(
        conn,
        "SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? "
        "ORDER BY ORDINAL_POSITION",
        schema,
        nome,
    )
    campos = [
        pa.field(c, tipo_arrow(t, p, e), nullable=(n == "YES"))
        for c, t, p, e, n in colunas
        if c != "rv"  # o rowversion do próprio staging não é dado de negócio
    ]
    return pa.schema(campos)


def _coluna(valores: list[Any], tipo: pa.DataType) -> pa.Array:
    if pa.types.is_decimal(tipo):
        valores = [
            Decimal(str(v)) if v is not None and not isinstance(v, Decimal) else v for v in valores
        ]
    return pa.array(valores, type=tipo)


def linhas_para_arrow(linhas: list[tuple[Any, ...]], esquema: pa.Schema) -> pa.Table:
    colunas = [
        _coluna([linha[i] for linha in linhas], campo.type) for i, campo in enumerate(esquema)
    ]
    return pa.Table.from_arrays(colunas, schema=esquema)


def extrair_tabela(
    conn: pyodbc.Connection, lake: Lake, tabela: str, execucao: str, marca: int
) -> dict[str, Any]:
    t0 = time.perf_counter()
    esquema = esquema_da_tabela(conn, tabela)
    cols = ", ".join(f"[{c}]" for c in esquema.names)
    linhas = db.consultar(
        conn, f"SELECT {cols} FROM {tabela} WHERE _rv_origem > ? ORDER BY _rv_origem", marca
    )
    total_staging = int(db.escalar(conn, f"SELECT COUNT(*) FROM {tabela}") or 0)
    resultado: dict[str, Any] = {
        "linhas_lidas": len(linhas),
        "marca_anterior": marca,
        "marca_nova": marca,
        "total_staging": total_staging,
        "arquivo": None,
    }
    if linhas:
        arrow = linhas_para_arrow(linhas, esquema)
        idx_rv = esquema.get_field_index("_rv_origem")
        nova_marca = max(int(linha[idx_rv]) for linha in linhas)
        destino = lake.escrever_parquet(
            arrow, "bronze", tabela, f"carga={execucao}", "parte-000.parquet"
        )
        escritas = lake.contar_parquet("bronze", tabela, f"carga={execucao}", "parte-000.parquet")
        if escritas != len(linhas):
            raise RuntimeError(f"{tabela}: lidas {len(linhas)} linhas, gravadas {escritas}")
        resultado.update(marca_nova=nova_marca, arquivo=destino, linhas_gravadas=escritas)
    resultado["segundos"] = round(time.perf_counter() - t0, 2)
    return resultado


def total_bronze(lake: Lake, tabela: str) -> int:
    """Soma das linhas de todas as cargas da tabela no bronze (para conferir com o staging)."""
    total = 0
    for pasta in lake.listar("bronze", tabela):
        if "carga=" not in pasta:
            continue
        for arq in lake.fs.ls(pasta, detail=False):
            if str(arq).endswith(".parquet"):
                with lake.fs.open(arq, "rb") as f:
                    total += int(pq.ParquetFile(f).metadata.num_rows)
    return total


def main() -> None:
    lake = abrir_lake()
    manifesto = novo_manifesto("bronze")
    marcas: dict[str, int] = lake.ler_json(CONTROLE, "marcas.json") or {}
    conn = db.conectar(conexao_staging())
    inicio = time.perf_counter()
    print(f"Bronze: staging → {lake.raiz}/bronze, carga {manifesto.execucao}\n")
    print(f"  {'tabela':34} {'lidas':>9} {'bronze total':>13} {'staging':>9} {'tempo':>7}")
    tot = 0
    try:
        for tabela in TABELAS:
            r = extrair_tabela(conn, lake, tabela, manifesto.execucao, int(marcas.get(tabela, 0)))
            marcas[tabela] = r["marca_nova"]
            acumulado = total_bronze(lake, tabela)
            # linhas distintas por chave no bronze = linhas do staging (o mesmo id pode aparecer em
            # várias cargas; a igualdade exata só vale enquanto não houver atualização entre cargas)
            r["bronze_total"] = acumulado
            r["conferencia"] = "ok" if acumulado >= r["total_staging"] else "FALTA"
            manifesto.registrar(tabela, **r)
            tot += r["linhas_lidas"]
            print(
                f"  {tabela:34} {r['linhas_lidas']:>9} {acumulado:>13} {r['total_staging']:>9} "
                f"{r['segundos']:>6.1f}s"
            )
    finally:
        conn.close()
    lake.escrever_json(marcas, CONTROLE, "marcas.json")
    lake.escrever_json(manifesto.fechar(), CONTROLE, "cargas", f"{manifesto.execucao}.json")
    faltas = [t for t, d in (manifesto.tabelas or {}).items() if d["conferencia"] != "ok"]
    print(
        f"\nConcluído em {time.perf_counter() - inicio:.1f}s: {tot} linhas novas no bronze; "
        f"manifesto em {CONTROLE}/cargas/{manifesto.execucao}.json"
    )
    if faltas:
        raise SystemExit(f"Conferência de contagens FALHOU em: {', '.join(faltas)}")
    if tot == 0:
        print("Nada mudou no staging desde a última carga do bronze.")
    print(f"Execução registrada às {datetime.now():%H:%M:%S}. Próximo: uv run silver-staging")


if __name__ == "__main__":
    main()
