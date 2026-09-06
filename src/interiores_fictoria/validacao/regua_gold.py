"""Régua da gold: o star schema tem de bater com a silver e com a história do negócio.

Uso: `uv run regua-gold`. Conferências de reconciliação (contagens e somas contra a silver),
integridade dimensional (nenhuma chave órfã), coerência interna (posição do funil no último
mês = fase atual) e o arco de conversão dentro das bandas do plano. Código de saída 1 em
qualquer reprovação.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import duckdb

from interiores_fictoria import duck
from interiores_fictoria.validacao import bandas


@dataclass
class Resultado:
    check: str
    observado: str
    ok: bool


def _um(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    v = con.execute(sql).fetchone()
    return float(v[0]) if v and v[0] is not None else float("nan")


def _igual(
    con: duckdb.DuckDBPyConnection, nome: str, a: str, b: str, tol: float = 0.0
) -> Resultado:
    va, vb = _um(con, a), _um(con, b)
    ok = abs(va - vb) <= tol
    return Resultado(nome, f"{va:,.2f} × {vb:,.2f}", ok)


def _zero(con: duckdb.DuckDBPyConnection, nome: str, sql: str) -> Resultado:
    v = _um(con, sql)
    return Resultado(nome, f"{v:,.0f}", v == 0)


ORFAOS: list[tuple[str, str, str, str]] = [
    # fato, coluna, dimensão, chave
    ("ft_orcamento", "sk_data_cadastro", "dim_calendario", "sk_data"),
    ("ft_orcamento", "sk_data_fechamento", "dim_calendario", "sk_data"),
    ("ft_orcamento", "sk_unidade", "dim_unidade", "sk_unidade"),
    ("ft_orcamento", "sk_vendedor", "dim_vendedor", "sk_vendedor"),
    ("ft_orcamento", "sk_cliente", "dim_cliente", "sk_cliente"),
    ("ft_orcamento", "sk_canal", "dim_canal", "sk_canal"),
    ("ft_orcamento", "sk_parceiro", "dim_parceiro", "sk_parceiro"),
    ("ft_orcamento", "sk_fase", "dim_fase", "sk_fase"),
    ("ft_orcamento", "sk_motivo_perda", "dim_motivo_perda", "sk_motivo_perda"),
    ("ft_orcamento", "sk_faixa_valor", "dim_faixa_valor", "sk_faixa_valor"),
    ("ft_venda", "sk_data_ganho", "dim_calendario", "sk_data"),
    ("ft_venda", "sk_forma_pagamento", "dim_forma_pagamento", "sk_forma_pagamento"),
    ("ft_comissao", "sk_data_competencia", "dim_calendario", "sk_data"),
    ("ft_comissao", "sk_parceiro", "dim_parceiro", "sk_parceiro"),
    ("ft_funil_posicao", "sk_data_posicao", "dim_calendario", "sk_data"),
    ("ft_funil_posicao", "sk_fase", "dim_fase", "sk_fase"),
    ("ft_orcamento_item", "sk_item", "dim_item", "sk_item"),
    ("ft_orcamento_item", "sk_ambiente", "dim_ambiente", "sk_ambiente"),
    ("ft_parcela", "sk_data_vencimento", "dim_calendario", "sk_data"),
    ("ft_follow_up", "sk_vendedor", "dim_vendedor", "sk_vendedor"),
]


def executar(con: duckdb.DuckDBPyConnection) -> list[Resultado]:
    r: list[Resultado] = []
    # --- reconciliação com a silver ---
    r.append(
        _igual(
            con,
            "ft_orcamento = orçamentos de venda da silver (linhas)",
            "SELECT COUNT(*) FROM g_ft_orcamento",
            "SELECT COUNT(*) FROM s_orcamento WHERE fl_conta_bi",
        )
    )
    r.append(
        _igual(
            con,
            "ft_venda = ganhos da silver (linhas)",
            "SELECT COUNT(*) FROM g_ft_venda",
            "SELECT COUNT(*) FROM s_orcamento WHERE fl_conta_bi AND grupo_fase = 'GANHO'",
        )
    )
    r.append(
        _igual(
            con,
            "ft_venda: soma do líquido = silver",
            "SELECT SUM(vl_liquido) FROM g_ft_venda",
            "SELECT SUM(vl_total_liquido) FROM s_orcamento WHERE fl_conta_bi AND grupo_fase = 'GANHO'",
            0.5,
        )
    )
    r.append(
        _igual(
            con,
            "ft_orcamento: soma do bruto = silver",
            "SELECT SUM(vl_bruto) FROM g_ft_orcamento",
            "SELECT SUM(vl_total_bruto) FROM s_orcamento WHERE fl_conta_bi",
            0.5,
        )
    )
    r.append(
        _igual(
            con,
            "ft_comissao: soma = silver (orçamentos de venda)",
            "SELECT SUM(vl_comissao) FROM g_ft_comissao",
            "SELECT SUM(c.vl_comissao) FROM s_comissao c JOIN s_orcamento o ON o.id = c.orcamento_id WHERE o.fl_conta_bi",
            0.5,
        )
    )
    r.append(
        _igual(
            con,
            "ft_orcamento_item: soma dos itens ativos = silver",
            "SELECT SUM(vl_total) FROM g_ft_orcamento_item WHERE fl_cancelado = 0",
            "SELECT SUM(vl_bruto_itens) FROM s_orcamento WHERE fl_conta_bi",
            0.5,
        )
    )
    r.append(
        _igual(
            con,
            "ft_parcela = parcelas ativas de orçamentos de venda",
            "SELECT COUNT(*) FROM g_ft_parcela",
            "SELECT COUNT(*) FROM s_parcela p JOIN s_recebimento rc ON rc.id = p.recebimento_id "
            "JOIN s_orcamento o ON o.id = rc.orcamento_id WHERE o.fl_conta_bi AND p.dt_cancelamento IS NULL",
        )
    )
    # --- grão ---
    r.append(
        _zero(
            con,
            "ft_orcamento: sk_orcamento duplicado",
            "SELECT COUNT(*) - COUNT(DISTINCT sk_orcamento) FROM g_ft_orcamento",
        )
    )
    r.append(
        _zero(
            con,
            "ft_venda: sk_orcamento duplicado",
            "SELECT COUNT(*) - COUNT(DISTINCT sk_orcamento) FROM g_ft_venda",
        )
    )
    r.append(
        _zero(
            con,
            "dim_cliente: sk duplicado",
            "SELECT COUNT(*) - COUNT(DISTINCT sk_cliente) FROM g_dim_cliente",
        )
    )
    r.append(
        _zero(
            con,
            "dim_calendario: sk duplicado",
            "SELECT COUNT(*) - COUNT(DISTINCT sk_data) FROM g_dim_calendario",
        )
    )
    # --- integridade dimensional ---
    for fato, col, dim, chave in ORFAOS:
        r.append(
            _zero(
                con,
                f"{fato}.{col} órfã em {dim}",
                f"SELECT COUNT(*) FROM g_{fato} f LEFT JOIN g_{dim} d ON d.{chave} = f.{col} WHERE d.{chave} IS NULL",
            )
        )
    # --- coerência interna ---
    r.append(
        _zero(
            con,
            "abertos com data de fechamento (≠ -1)",
            "SELECT COUNT(*) FROM g_ft_orcamento WHERE fl_aberto = 1 AND sk_data_fechamento <> -1",
        )
    )
    r.append(
        _zero(
            con,
            "fechados sem data de fechamento",
            "SELECT COUNT(*) FROM g_ft_orcamento WHERE fl_fechado = 1 AND sk_data_fechamento = -1",
        )
    )
    r.append(
        _igual(
            con,
            "funil: posição do último mês = fase atual (abertos)",
            "SELECT SUM(qtd_orcamentos) FROM g_ft_funil_posicao WHERE grupo_fase = 'ABERTO' "
            "AND sk_data_posicao = (SELECT MAX(sk_data_posicao) FROM g_ft_funil_posicao)",
            "SELECT SUM(fl_aberto) FROM g_ft_orcamento",
        )
    )
    r.append(
        _igual(
            con,
            "funil: posição do último mês = fase atual (ganhos)",
            "SELECT SUM(qtd_orcamentos) FROM g_ft_funil_posicao WHERE grupo_fase = 'GANHO' "
            "AND sk_data_posicao = (SELECT MAX(sk_data_posicao) FROM g_ft_funil_posicao)",
            "SELECT SUM(fl_ganho) FROM g_ft_orcamento",
        )
    )
    r.append(
        _igual(
            con,
            "dim_calendario cobre 2021-01-01 a 2027-12-31 (dias + membro -1)",
            "SELECT COUNT(*) FROM g_dim_calendario",
            "SELECT 365 * 6 + 366 + 1",  # 2021-2027: um bissexto (2024)
        )
    )
    r.append(
        _zero(
            con,
            "faixas de SLA: lacuna ou sobreposição entre faixas",
            """SELECT COUNT(*) FROM g_dim_faixa_sla a JOIN g_dim_faixa_sla b
                      ON a.tipo = b.tipo AND b.ordem = a.ordem + 1
                      WHERE a.limite_superior_inclusivo <> b.limite_inferior_exclusivo""",
        )
    )
    # --- a história do negócio, lida da gold ---
    conv = con.execute(
        """SELECT ano, SUM(fl_ganho) * 1.0 / NULLIF(SUM(fl_fechado), 0) FROM g_ft_orcamento
           WHERE fl_fechado = 1 AND (ano >= 2026 OR dt_cadastro <= (SELECT MAX(dt_cadastro) FROM g_ft_orcamento) - INTERVAL 180 DAY)
           GROUP BY ano ORDER BY ano"""
    ).fetchall()
    for ano, taxa in conv:
        banda = bandas.CONVERSAO_POR_ANO.get(int(ano))
        if banda:
            r.append(
                Resultado(
                    f"conversão {ano} dentro da banda do plano",
                    f"{float(taxa):.3f}",
                    banda[0] <= float(taxa) <= banda[1],
                )
            )
    return r


def main() -> None:
    con, lake = duck.conectar()
    duck.registrar_silver(con, lake)
    duck.registrar_gold(con, lake)
    resultados = executar(con)
    largura = max(len(x.check) for x in resultados)
    reprovados = [x for x in resultados if not x.ok]
    print(f"\nRégua da gold — {len(resultados)} checks\n")
    for res in resultados:
        print(f"  {'OK   ' if res.ok else 'FALHA'}  {res.check.ljust(largura)}  {res.observado}")
    print(f"\n{len(resultados) - len(reprovados)} aprovados, {len(reprovados)} reprovados.")
    if reprovados:
        print("Veredito: gold REPROVADA.")
        sys.exit(1)
    print("Veredito: gold APROVADA. Próximo: uv run carga-dw")


if __name__ == "__main__":
    main()
