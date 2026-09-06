"""Carga incremental origem → staging por marca d'água de `rowversion`.

Uso: `uv run carga-staging`. Para cada tabela (pais antes de filhos), lê da origem só as
linhas com `rv` maior que a marca d'água da carga anterior, aplica no staging por MERGE
(insere as novas, atualiza as alteradas) e avança a marca. A primeira carga é a carga
completa; as seguintes tocam apenas o delta, e é isso que tira o peso do BI de cima da
produção. Cada execução fica registrada em `controle.carga`, por tabela, com contagens.

O staging tem as mesmas tabelas da origem (mesmo DDL) mais as colunas de controle
`_carregado_em`, `_origem` e `_rv_origem`, criadas por este carregador na primeira execução.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import pyodbc

from interiores_fictoria import db
from interiores_fictoria.config import conexao_origem, conexao_staging

# Ordem de carga: pais antes de filhos (FKs do staging são as mesmas da origem).
TABELAS: tuple[str, ...] = (
    "cadastro.unidade",
    "cadastro.usuario",
    "cadastro.origem_contato",
    "cadastro.parceiro",
    "cadastro.cliente",
    "cadastro.endereco",
    "cadastro.tipo_orcamento",
    "cadastro.fase",
    "cadastro.motivo_perda",
    "cadastro.status_etapa",
    "cadastro.ambiente",
    "cadastro.categoria_item",
    "cadastro.fornecedor",
    "cadastro.item_catalogo",
    "cadastro.forma_pagamento",
    "cadastro.condicao_parcelamento",
    "comercial.orcamento",
    "comercial.orcamento_item",
    "comercial.orcamento_fase_hist",
    "comercial.orcamento_etapa",
    "comercial.follow_up",
    "comercial.orcamento_historico",
    "comercial.auditoria_orcamento",
    "financeiro.recebimento",
    "financeiro.parcela",
    "financeiro.pagamento",
    "financeiro.comissao",
    "obra.medicao",
    "obra.instalacao",
    "obra.instalacao_historico",
)
COLUNAS_CONTROLE = ("_carregado_em", "_origem", "_rv_origem")
MARCA_ZERO = 0

DDL_CONTROLE = """
IF SCHEMA_ID('controle') IS NULL EXEC('CREATE SCHEMA controle');
IF OBJECT_ID('controle.marca_dagua', 'U') IS NULL
CREATE TABLE controle.marca_dagua (
    tabela         varchar(80)   NOT NULL CONSTRAINT pk_marca_dagua PRIMARY KEY,
    rv             bigint        NOT NULL,
    atualizado_em  datetime2(0)  NOT NULL
);
IF OBJECT_ID('controle.carga', 'U') IS NULL
CREATE TABLE controle.carga (
    id              bigint IDENTITY(1,1) NOT NULL CONSTRAINT pk_carga PRIMARY KEY,
    execucao        datetime2(0)  NOT NULL,
    tabela          varchar(80)   NOT NULL,
    inicio          datetime2(3)  NOT NULL,
    fim             datetime2(3)  NOT NULL,
    lidas           int           NOT NULL,
    inseridas       int           NOT NULL,
    atualizadas     int           NOT NULL,
    marca_anterior  bigint        NOT NULL,
    marca_nova      bigint        NOT NULL
);
"""


@dataclass(frozen=True)
class ResultadoTabela:
    tabela: str
    lidas: int
    inseridas: int
    atualizadas: int
    segundos: float


def _preparar_staging(stg: pyodbc.Connection) -> None:
    db.executar(stg, DDL_CONTROLE)
    for tabela in TABELAS:
        schema, nome = tabela.split(".")
        existentes = {
            c[0]
            for c in db.consultar(
                stg,
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
                schema,
                nome,
            )
        }
        if "_carregado_em" not in existentes:
            db.executar(
                stg,
                f"ALTER TABLE {tabela} ADD _carregado_em datetime2(0) NOT NULL "
                f"CONSTRAINT df_{nome}_carregado DEFAULT SYSDATETIME()",
            )
        if "_origem" not in existentes:
            db.executar(
                stg,
                f"ALTER TABLE {tabela} ADD _origem varchar(40) NOT NULL "
                f"CONSTRAINT df_{nome}_origem DEFAULT 'db_fictoria'",
            )
        if "_rv_origem" not in existentes:
            db.executar(stg, f"ALTER TABLE {tabela} ADD _rv_origem bigint NULL")
    stg.commit()


def _colunas_origem(origem: pyodbc.Connection, tabela: str) -> list[str]:
    schema, nome = tabela.split(".")
    linhas = db.consultar(
        origem,
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
        schema,
        nome,
    )
    return [c[0] for c in linhas if c[0] != "rv"]


def _identidade(stg: pyodbc.Connection, tabela: str) -> bool:
    return bool(
        db.escalar(
            stg, "SELECT COUNT(*) FROM sys.identity_columns WHERE object_id = OBJECT_ID(?)", tabela
        )
    )


def _normalizar(valores: tuple[Any, ...]) -> tuple[Any, ...]:
    """Decimal vira float: o pyodbc com fast_executemany rejeita Decimal ("loses precision")."""
    return tuple(float(v) if isinstance(v, Decimal) else v for v in valores)


def _marca(stg: pyodbc.Connection, tabela: str) -> int:
    v = db.escalar(stg, "SELECT rv FROM controle.marca_dagua WHERE tabela = ?", tabela)
    return int(v) if v is not None else MARCA_ZERO


def carregar_tabela(
    origem: pyodbc.Connection,
    stg: pyodbc.Connection,
    tabela: str,
    nome_origem: str,
    execucao: datetime,
) -> ResultadoTabela:
    t0 = time.perf_counter()
    inicio = datetime.now()
    marca = _marca(stg, tabela)
    colunas = _colunas_origem(origem, tabela)
    sel = ", ".join(f"[{c}]" for c in colunas)
    linhas = db.consultar(
        origem,
        f"SELECT {sel}, CAST(rv AS bigint) FROM {tabela} "
        "WHERE rv > CAST(? AS binary(8)) ORDER BY rv",
        marca,
    )
    inseridas = atualizadas = 0
    nova_marca = marca
    if linhas:
        dados = [(*_normalizar(linha[:-1]), int(linha[-1]), nome_origem) for linha in linhas]
        nova_marca = int(linhas[-1][-1])
        r = db.sincronizar(
            stg,
            tabela,
            [*colunas, "_rv_origem", "_origem"],
            dados,
            identidade=_identidade(stg, tabela),
            colunas_extra_update={"_carregado_em": "SYSDATETIME()"},
        )
        inseridas, atualizadas = r.inseridas, r.atualizadas
        db.executar(
            stg,
            """
            MERGE controle.marca_dagua AS t
            USING (SELECT ? AS tabela, ? AS rv) AS s ON t.tabela = s.tabela
            WHEN MATCHED THEN UPDATE SET rv = s.rv, atualizado_em = SYSDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (tabela, rv, atualizado_em) VALUES (s.tabela, s.rv, SYSDATETIME());
            """,
            tabela,
            nova_marca,
        )
    db.executar(
        stg,
        """
        INSERT INTO controle.carga (execucao, tabela, inicio, fim, lidas, inseridas, atualizadas,
                                    marca_anterior, marca_nova)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        execucao,
        tabela,
        inicio,
        datetime.now(),
        len(linhas),
        inseridas,
        atualizadas,
        marca,
        nova_marca,
    )
    stg.commit()
    return ResultadoTabela(tabela, len(linhas), inseridas, atualizadas, time.perf_counter() - t0)


def _recriar(stg: pyodbc.Connection) -> None:
    """Zera o staging (filhos antes dos pais) e as marcas d'água: a próxima carga é completa."""
    for tabela in reversed(TABELAS):
        db.executar(stg, f"DELETE FROM {tabela}")
    db.executar(stg, "DELETE FROM controle.marca_dagua")
    db.executar(stg, "DELETE FROM controle.carga")
    stg.commit()


def main() -> None:
    p = argparse.ArgumentParser(
        description="Carga incremental origem → staging (marca d'água rowversion)."
    )
    p.add_argument(
        "--recriar", action="store_true", help="zera o staging e as marcas antes de carregar"
    )
    args = p.parse_args()
    execucao = datetime.now().replace(microsecond=0)
    nome_origem = os.environ.get("ORIGEM_DB", "db_fictoria")
    origem = db.conectar(conexao_origem())
    stg = db.conectar(conexao_staging())
    inicio = time.perf_counter()
    try:
        _preparar_staging(stg)
        if args.recriar:
            print("  (--recriar) zerando o staging e as marcas d'água ...")
            _recriar(stg)
        print(f"Carga incremental {nome_origem} → staging, execução {execucao:%Y-%m-%d %H:%M:%S}\n")
        print(f"  {'tabela':34} {'lidas':>9} {'inseridas':>10} {'atualizadas':>12} {'tempo':>7}")
        tot_l = tot_i = tot_u = 0
        for tabela in TABELAS:
            r = carregar_tabela(origem, stg, tabela, nome_origem, execucao)
            tot_l += r.lidas
            tot_i += r.inseridas
            tot_u += r.atualizadas
            print(
                f"  {r.tabela:34} {r.lidas:>9} {r.inseridas:>10} {r.atualizadas:>12}"
                f" {r.segundos:>6.1f}s"
            )
        print(
            f"\nConcluído em {time.perf_counter() - inicio:.1f}s: {tot_l} linhas lidas da origem, "
            f"{tot_i} inseridas e {tot_u} atualizadas no staging."
        )
        if tot_l == 0:
            print("Nada mudou na origem desde a última carga: só as marcas d'água foram lidas.")
    finally:
        origem.close()
        stg.close()


if __name__ == "__main__":
    main()
