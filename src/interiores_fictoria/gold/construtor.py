"""Gold: constrói o star schema a partir da silver e grava em parquet particionado por ano.

Uso: `uv run gold-staging`. Dimensões em `gold/<dim>/parte-000.parquet`; fatos em
`gold/<fato>/ano=YYYY/parte-000.parquet` (partição hive). A partição por ano é a unidade
de carga e de auditoria: é ela que o warehouse carrega e confere uma a uma.
"""

from __future__ import annotations

import time
from typing import Any

import duckdb

from interiores_fictoria import duck
from interiores_fictoria.gold import modelo
from interiores_fictoria.lake import Lake, novo_manifesto


def _gravar_dim(con: duckdb.DuckDBPyConnection, lake: Lake, nome: str, sql: str) -> int:
    lake.apagar("gold", nome)
    lake.fs.makedirs(lake.caminho("gold", nome), exist_ok=True)
    destino = lake.caminho("gold", nome, "parte-000.parquet")
    con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return int(con.execute(f"SELECT COUNT(*) FROM read_parquet('{destino}')").fetchone()[0])  # type: ignore[index]


def _gravar_fato(con: duckdb.DuckDBPyConnection, lake: Lake, nome: str, sql: str) -> dict[int, int]:
    lake.apagar("gold", nome)
    lake.fs.makedirs(lake.caminho("gold", nome), exist_ok=True)
    con.execute(f"CREATE OR REPLACE TEMP TABLE _fato AS {sql}")
    anos = [
        int(a) for (a,) in con.execute("SELECT DISTINCT ano FROM _fato ORDER BY ano").fetchall()
    ]
    por_ano: dict[int, int] = {}
    for ano in anos:
        pasta = lake.caminho("gold", nome, f"ano={ano}")
        lake.fs.makedirs(pasta, exist_ok=True)
        destino = f"{pasta}/parte-000.parquet"
        con.execute(
            f"COPY (SELECT * EXCLUDE (ano) FROM _fato WHERE ano = {ano}) TO '{destino}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        por_ano[ano] = int(
            con.execute(f"SELECT COUNT(*) FROM read_parquet('{destino}')").fetchone()[0]
        )  # type: ignore[index]
    con.execute("DROP TABLE _fato")
    return por_ano


def main() -> None:
    inicio = time.perf_counter()
    con, lake = duck.conectar()
    duck.registrar_silver(con, lake)
    con.execute(modelo.MACROS)
    manifesto = novo_manifesto("gold")
    print(f"Gold: silver → {lake.raiz}/gold\n")
    print(f"  {'dimensão':24} {'linhas':>9} {'tempo':>7}")
    for nome, sql in modelo.DIMENSOES.items():
        t0 = time.perf_counter()
        n = _gravar_dim(con, lake, nome, sql)
        manifesto.registrar(nome, tipo="dimensao", linhas=n)
        print(f"  {nome:24} {n:>9} {time.perf_counter() - t0:>6.1f}s")
    print(f"\n  {'fato':24} {'linhas':>9} {'partições (ano)':>34} {'tempo':>7}")
    resumo: dict[str, Any] = {}
    for nome, sql in modelo.FATOS.items():
        t0 = time.perf_counter()
        por_ano = _gravar_fato(con, lake, nome, sql)
        total = sum(por_ano.values())
        manifesto.registrar(nome, tipo="fato", linhas=total, por_ano=por_ano)
        resumo[nome] = total
        anos = ", ".join(f"{a}" for a in por_ano)
        print(f"  {nome:24} {total:>9} {anos:>34} {time.perf_counter() - t0:>6.1f}s")
    lake.escrever_json(
        manifesto.fechar(), "gold", "_controle", f"construcao_{manifesto.execucao}.json"
    )
    print(
        f"\nConcluído em {time.perf_counter() - inicio:.1f}s: {len(modelo.DIMENSOES)} dimensões e "
        f"{len(modelo.FATOS)} fatos ({sum(resumo.values())} linhas de fato). Valide com: uv run regua-gold"
    )


if __name__ == "__main__":
    main()
