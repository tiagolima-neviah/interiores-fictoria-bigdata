"""DuckDB sobre o lake: views do bronze (estado corrente por chave), silver e gold.

O bronze é append-only por carga; a view `b_<tabela>` entrega o estado corrente de cada
chave (maior `_rv_origem` vence), que é o que a auditoria de qualidade e a silver leem.
Silver e gold são lidas direto dos seus diretórios em parquet.
"""

from __future__ import annotations

import duckdb

from interiores_fictoria.lake import Lake, abrir_lake
from interiores_fictoria.staging.carga_incremental import TABELAS


def nome_curto(tabela: str) -> str:
    """`comercial.orcamento` → `orcamento` (os nomes são únicos entre os schemas)."""
    return tabela.split(".")[1]


def conectar(lake: Lake | None = None) -> tuple[duckdb.DuckDBPyConnection, Lake]:
    lake = lake or abrir_lake()
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for tabela in TABELAS:
        if not lake.listar("bronze", tabela):
            continue
        padrao = lake.caminho("bronze", tabela, "carga=*", "*.parquet")
        con.execute(
            f"""
            CREATE OR REPLACE VIEW b_{nome_curto(tabela)} AS
            SELECT * EXCLUDE (carga)
            FROM read_parquet('{padrao}', hive_partitioning = true, union_by_name = true)
            QUALIFY row_number() OVER (PARTITION BY id ORDER BY _rv_origem DESC, carga DESC) = 1
            """
        )
    return con, lake


def registrar_silver(con: duckdb.DuckDBPyConnection, lake: Lake) -> None:
    for pasta in lake.listar("silver"):
        nome = pasta.rstrip("/").rsplit("/", 1)[-1]
        if nome.startswith("_"):
            continue
        con.execute(
            f"CREATE OR REPLACE VIEW s_{nome} AS "
            f"SELECT * FROM read_parquet('{lake.caminho('silver', nome, '*.parquet')}')"
        )


def registrar_gold(con: duckdb.DuckDBPyConnection, lake: Lake) -> None:
    for pasta in lake.listar("gold"):
        nome = pasta.rstrip("/").rsplit("/", 1)[-1]
        if nome.startswith("_"):
            continue
        con.execute(
            f"CREATE OR REPLACE VIEW g_{nome} AS SELECT * FROM read_parquet("
            f"'{lake.caminho('gold', nome, '**', '*.parquet')}', hive_partitioning = true)"
        )
