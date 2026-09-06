"""Acesso ao SQL Server via pyodbc: conexão, lotes e sincronização por MERGE.

A peça central é `sincronizar`: recebe o estado desejado de uma tabela (linhas com
chave primária explícita) e aplica no banco só o que difere, via tabela temporária
e MERGE. Linha nova é inserida, linha alterada é atualizada, linha igual não é
tocada. É isso que faz o `rowversion` de cada linha mudar apenas quando a linha
mudou, e é o que permite ao staging incremental enxergar o delta exato.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pyodbc

TAMANHO_LOTE = 20_000


@dataclass(frozen=True)
class ResultadoSync:
    tabela: str
    recebidas: int
    inseridas: int
    atualizadas: int


def conectar(conexao: str, *, autocommit: bool = False) -> pyodbc.Connection:
    conn = pyodbc.connect(conexao, autocommit=autocommit, timeout=15)
    return conn


def executar(conn: pyodbc.Connection, sql: str, *params: Any) -> None:
    cur = conn.cursor()
    try:
        cur.execute(sql, *params)
    finally:
        cur.close()


def consultar(conn: pyodbc.Connection, sql: str, *params: Any) -> list[tuple[Any, ...]]:
    cur = conn.cursor()
    try:
        cur.execute(sql, *params)
        return [tuple(linha) for linha in cur.fetchall()]
    finally:
        cur.close()


def escalar(conn: pyodbc.Connection, sql: str, *params: Any) -> Any:
    linhas = consultar(conn, sql, *params)
    return linhas[0][0] if linhas else None


def _lotes(linhas: Sequence[Sequence[Any]], tamanho: int) -> Iterable[Sequence[Sequence[Any]]]:
    for i in range(0, len(linhas), tamanho):
        yield linhas[i : i + tamanho]


def sincronizar(
    conn: pyodbc.Connection,
    tabela: str,
    colunas: Sequence[str],
    linhas: Sequence[Sequence[Any]],
    *,
    pk: str = "id",
    identidade: bool = True,
    colunas_extra_update: dict[str, str] | None = None,
) -> ResultadoSync:
    """Aplica `linhas` (estado desejado) em `tabela` por MERGE sobre a chave `pk`.

    `colunas` inclui a chave. Colunas que existem na tabela e não vêm em `colunas`
    (ex.: `dt_atualizacao`, `rv`, `_carregado_em`) ficam a cargo do banco:
    `colunas_extra_update` permite fixar expressões SQL para elas no UPDATE
    (ex.: {"dt_atualizacao": "SYSDATETIME()"}). A comparação de mudança é
    null-safe (EXCEPT), então linha idêntica não gera UPDATE nem novo rowversion.
    """
    cur = conn.cursor()
    cur.fast_executemany = True
    try:
        cols = ", ".join(f"[{c}]" for c in colunas)
        cols_sem_pk = [c for c in colunas if c != pk]
        # Tabela temporária com os mesmos tipos (CAST na PK tira a propriedade IDENTITY).
        sel = ", ".join(
            f"CAST([{c}] AS bigint) AS [{c}]" if c == pk and identidade else f"[{c}]"
            for c in colunas
        )
        cur.execute("IF OBJECT_ID('tempdb..#sync') IS NOT NULL DROP TABLE #sync")
        cur.execute(f"SELECT TOP 0 {sel} INTO #sync FROM {tabela}")
        marcadores = ", ".join("?" for _ in colunas)
        for lote in _lotes(linhas, TAMANHO_LOTE):
            cur.executemany(f"INSERT INTO #sync ({cols}) VALUES ({marcadores})", list(lote))
        cur.execute(f"CREATE UNIQUE CLUSTERED INDEX ix_sync ON #sync ([{pk}])")

        cmp_t = ", ".join(f"t.[{c}]" for c in cols_sem_pk)
        cmp_s = ", ".join(f"s.[{c}]" for c in cols_sem_pk)
        sets = [f"t.[{c}] = s.[{c}]" for c in cols_sem_pk]
        for col, expr in (colunas_extra_update or {}).items():
            sets.append(f"t.[{col}] = {expr}")
        ins_cols = cols
        ins_vals = ", ".join(f"s.[{c}]" for c in colunas)
        clausula_update = ""
        if cols_sem_pk:
            clausula_update = (
                f"WHEN MATCHED AND EXISTS (SELECT {cmp_t} EXCEPT SELECT {cmp_s}) "
                f"THEN UPDATE SET {', '.join(sets)} "
            )
        sql = (
            "SET NOCOUNT ON; DECLARE @acoes TABLE (acao varchar(10)); "
            + (f"SET IDENTITY_INSERT {tabela} ON; " if identidade else "")
            + f"MERGE {tabela} WITH (HOLDLOCK) AS t USING #sync AS s ON t.[{pk}] = s.[{pk}] "
            + clausula_update
            + f"WHEN NOT MATCHED BY TARGET THEN INSERT ({ins_cols}) VALUES ({ins_vals}) "
            + "OUTPUT $action INTO @acoes; "
            + (f"SET IDENTITY_INSERT {tabela} OFF; " if identidade else "")
            + "SELECT SUM(CASE WHEN acao = 'INSERT' THEN 1 ELSE 0 END), "
            + "SUM(CASE WHEN acao = 'UPDATE' THEN 1 ELSE 0 END) FROM @acoes;"
        )
        cur.execute(sql)
        while cur.description is None and cur.nextset():
            pass
        linha = cur.fetchone()
        inseridas = int(linha[0] or 0) if linha else 0
        atualizadas = int(linha[1] or 0) if linha else 0
        cur.execute("DROP TABLE #sync")
        conn.commit()
        return ResultadoSync(tabela, len(linhas), inseridas, atualizadas)
    finally:
        cur.close()
