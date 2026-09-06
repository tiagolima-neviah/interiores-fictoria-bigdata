"""Régua de validação da origem sintética: roda os checks contra o SQL Server e dá o veredito.

Uso: `uv run regua-origem` (ou `--staging` para validar o espelho). Saída: um relatório por
check (observado × banda × veredito) e código de saída 1 se qualquer check reprovar:
reprovou, regenera-se a base. As bandas vivem em `bandas.py`, versionadas.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import pyodbc

from interiores_fictoria import db
from interiores_fictoria.config import conexao_origem, conexao_staging
from interiores_fictoria.validacao import bandas


@dataclass
class Resultado:
    check: str
    observado: str
    banda: str
    ok: bool


def _avaliar(nome: str, valor: float | None, banda: bandas.Banda, fmt: str = "{:.4f}") -> Resultado:
    faixa = f"[{fmt.format(banda[0])} .. {fmt.format(banda[1])}]"
    if valor is None:
        return Resultado(nome, "sem dados", faixa, ok=False)
    return Resultado(nome, fmt.format(valor), faixa, banda[0] <= valor <= banda[1])


def _num(conn: pyodbc.Connection, sql: str) -> float | None:
    v = db.escalar(conn, sql)
    return None if v is None else float(v)


def _por_ano(
    conn: pyodbc.Connection, nome: str, sql: str, por_ano: dict[int, bandas.Banda], fmt: str
) -> list[Resultado]:
    observados = {int(a): float(v) for a, v in db.consultar(conn, sql) if v is not None}
    return [
        _avaliar(f"{nome} {ano}", observados.get(ano), banda, fmt)
        for ano, banda in sorted(por_ano.items())
    ]


# Orçamentos que o BI considera: tipo Venda, não cancelados.
VENDA = "o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL"
# Data corrente do universo: o último cadastro (não depende do relógio da máquina).
T = "(SELECT MAX(dt_cadastro) FROM comercial.orcamento)"


def _share(cond: str, extra_from: str = "", where: str = VENDA) -> str:
    """AVG de um caso booleano sobre os orçamentos de venda (com joins opcionais)."""
    return (
        f"SELECT AVG(CASE WHEN {cond} THEN 1.0 ELSE 0.0 END) "
        f"FROM comercial.orcamento o {extra_from} WHERE {where}"
    )


def _percentil(p: float, expr: str, extra_from: str = "", where: str = VENDA) -> str:
    return (
        f"SELECT DISTINCT PERCENTILE_CONT({p}) WITHIN GROUP (ORDER BY {expr}) OVER () "
        f"FROM comercial.orcamento o {extra_from} WHERE {where}"
    )


def executar(conexao: str) -> list[Resultado]:
    r: list[Resultado] = []
    conn = db.conectar(conexao)
    try:
        # --- volumes ---
        r += _por_ano(
            conn,
            "orçamentos de venda",
            f"SELECT YEAR(o.dt_cadastro), COUNT(*) FROM comercial.orcamento o WHERE {VENDA} "
            "GROUP BY YEAR(o.dt_cadastro)",
            bandas.ORCAMENTOS_POR_ANO,
            "{:.0f}",
        )
        r.append(
            _avaliar(
                "total de linhas em orcamento_item",
                _num(conn, "SELECT COUNT(*) FROM comercial.orcamento_item"),
                bandas.TOTAL_ORCAMENTO_ITEM,
                "{:.0f}",
            )
        )
        r.append(
            _avaliar(
                "total de linhas em auditoria_orcamento",
                _num(conn, "SELECT COUNT(*) FROM comercial.auditoria_orcamento"),
                bandas.TOTAL_AUDITORIA,
                "{:.0f}",
            )
        )
        # --- o arco: anos fechados com 180 dias de maturidade; 2026 sobre fechados ---
        r += _por_ano(
            conn,
            "conversão sobre fechados",
            f"""
            SELECT YEAR(o.dt_cadastro), AVG(CASE WHEN o.fase_id = 6 THEN 1.0 ELSE 0.0 END)
            FROM comercial.orcamento o
            WHERE {VENDA} AND o.fase_id IN (6, 7)
              AND (YEAR(o.dt_cadastro) >= 2026 OR o.dt_cadastro <= DATEADD(day, -180, {T}))
            GROUP BY YEAR(o.dt_cadastro)
            """,
            bandas.CONVERSAO_POR_ANO,
            "{:.3f}",
        )
        r.append(
            _avaliar(
                "carteira aberta em 2026 (share)",
                _num(
                    conn,
                    _share(
                        "f.grupo = 'ABERTO'",
                        "JOIN cadastro.fase f ON f.id = o.fase_id",
                        f"{VENDA} AND YEAR(o.dt_cadastro) = 2026",
                    ),
                ),
                bandas.SHARE_ABERTO_2026,
                "{:.3f}",
            )
        )
        # --- equipe ---
        r += _por_ano(
            conn,
            "vendedores com orçamento",
            f"SELECT YEAR(o.dt_cadastro), COUNT(DISTINCT o.vendedor_id) FROM comercial.orcamento o "
            f"WHERE {VENDA} GROUP BY YEAR(o.dt_cadastro)",
            bandas.VENDEDORES_POR_ANO,
            "{:.0f}",
        )
        # --- canais e parceiros ---
        canal_join = "JOIN cadastro.origem_contato oc ON oc.id = o.origem_contato_id"
        for grupo, ano, banda in [
            ("ARQUITETOS", 2021, bandas.SHARE_ARQUITETOS_2021),
            ("ARQUITETOS", 2026, bandas.SHARE_ARQUITETOS_2026),
            ("CANAL_PROPRIO", 2021, bandas.SHARE_CANAL_PROPRIO_2021),
            ("CANAL_PROPRIO", 2026, bandas.SHARE_CANAL_PROPRIO_2026),
        ]:
            r.append(
                _avaliar(
                    f"share {grupo} {ano}",
                    _num(
                        conn,
                        _share(
                            f"oc.grupo = '{grupo}'",
                            canal_join,
                            f"{VENDA} AND YEAR(o.dt_cadastro) = {ano}",
                        ),
                    ),
                    banda,
                    "{:.3f}",
                )
            )
        r.append(
            _avaliar(
                "share com parceiro cadastrado 2026",
                _num(
                    conn,
                    _share(
                        "o.parceiro_id IS NOT NULL", "", f"{VENDA} AND YEAR(o.dt_cadastro) = 2026"
                    ),
                ),
                bandas.SHARE_COM_PARCEIRO_2026,
                "{:.3f}",
            )
        )
        # --- sazonalidade ---
        r.append(
            _avaliar(
                "sazonalidade (ago-nov) / (jan-fev), 2021-2025",
                _num(
                    conn,
                    f"""
                SELECT SUM(CASE WHEN MONTH(o.dt_cadastro) IN (8, 9, 10, 11) THEN 1.0 ELSE 0.0 END)
                     / NULLIF(SUM(CASE WHEN MONTH(o.dt_cadastro) IN (1, 2)
                                       THEN 1.0 ELSE 0.0 END), 0)
                FROM comercial.orcamento o
                WHERE {VENDA} AND YEAR(o.dt_cadastro) BETWEEN 2021 AND 2025
            """,
                ),
                bandas.RAZAO_SAZONAL,
                "{:.2f}",
            )
        )
        # --- valores ---
        r.append(
            _avaliar(
                "ticket bruto mediana",
                _num(
                    conn,
                    _percentil(0.5, "o.vl_total_bruto", "", f"{VENDA} AND o.vl_total_bruto > 0"),
                ),
                bandas.TICKET_BRUTO_MEDIANA,
                "{:.0f}",
            )
        )
        r.append(
            _avaliar(
                "ticket bruto p90",
                _num(
                    conn,
                    _percentil(0.9, "o.vl_total_bruto", "", f"{VENDA} AND o.vl_total_bruto > 0"),
                ),
                bandas.TICKET_BRUTO_P90,
                "{:.0f}",
            )
        )
        r.append(
            _avaliar(
                "venda líquida mediana (ganhos)",
                _num(
                    conn,
                    _percentil(
                        0.5,
                        "o.vl_total_liquido",
                        "",
                        f"{VENDA} AND o.fase_id = 6 AND o.vl_total_liquido > 0",
                    ),
                ),
                bandas.VENDA_LIQUIDA_MEDIANA,
                "{:.0f}",
            )
        )
        r.append(
            _avaliar(
                "desconto médio nas vendas",
                _num(
                    conn,
                    f"""
                SELECT 1 - SUM(o.vl_total_liquido) / NULLIF(SUM(o.vl_total_bruto), 0)
                FROM comercial.orcamento o WHERE {VENDA} AND o.fase_id = 6
            """,
                ),
                bandas.DESCONTO_MEDIO_VENDAS,
                "{:.3f}",
            )
        )
        r.append(
            _avaliar(
                "comissão do vendedor / líquido (vendas)",
                _num(
                    conn,
                    f"""
                SELECT SUM(o.vl_comissao_vendedor) / NULLIF(SUM(o.vl_total_liquido), 0)
                FROM comercial.orcamento o WHERE {VENDA} AND o.fase_id = 6
            """,
                ),
                bandas.COMISSAO_VENDEDOR_SOBRE_LIQUIDO,
                "{:.4f}",
            )
        )
        # --- prazos (pela trilha de fases, que não tem sentinela) ---
        for nome, fase, banda in [
            ("dias até fechar mediana (ganhos)", 6, bandas.DIAS_FECHAR_GANHO),
            ("dias até fechar mediana (perdidos)", 7, bandas.DIAS_FECHAR_PERDIDO),
        ]:
            r.append(
                _avaliar(
                    nome,
                    _num(
                        conn,
                        _percentil(
                            0.5,
                            "DATEDIFF(day, o.dt_cadastro, h.dt_entrada)",
                            "JOIN comercial.orcamento_fase_hist h "
                            f"ON h.orcamento_id = o.id AND h.fase_id = {fase}",
                        ),
                    ),
                    banda,
                    "{:.0f}",
                )
            )
        # --- clientes ---
        r.append(
            _avaliar(
                "clientes recorrentes (share)",
                _num(
                    conn,
                    f"""
                SELECT AVG(CASE WHEN n > 1 THEN 1.0 ELSE 0.0 END)
                FROM (SELECT o.cliente_id, COUNT(*) AS n FROM comercial.orcamento o
                      WHERE {VENDA} GROUP BY o.cliente_id) c
            """,
                ),
                bandas.SHARE_CLIENTES_RECORRENTES,
                "{:.3f}",
            )
        )
        # --- sujeira ---
        fechados = f"{VENDA} AND o.fase_id IN (6, 7)"
        r.append(
            _avaliar(
                "sujeira: data-sentinela no fechamento",
                _num(conn, _share("o.dt_finalizou = '1900-01-01'", "", fechados)),
                bandas.SUJEIRA_DATA_SENTINELA,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "sujeira: fechou antes de cadastrar",
                _num(
                    conn,
                    _share(
                        "o.dt_finalizou < o.dt_cadastro AND o.dt_finalizou > '1900-01-01'",
                        "",
                        fechados,
                    ),
                ),
                bandas.SUJEIRA_FECHOU_ANTES_CADASTRO,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "sujeira: orçamento de valor zero",
                _num(conn, _share("o.vl_total_bruto = 0")),
                bandas.SUJEIRA_VALOR_ZERO,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "orçamentos sem follow-up (share)",
                _num(
                    conn,
                    _share(
                        "f.orcamento_id IS NULL",
                        "LEFT JOIN (SELECT DISTINCT orcamento_id FROM comercial.follow_up) f "
                        "ON f.orcamento_id = o.id",
                    ),
                ),
                bandas.SHARE_SEM_FOLLOW_UP,
                "{:.3f}",
            )
        )
        r.append(
            _avaliar(
                "ganhos sem etapas de execução (share)",
                _num(
                    conn,
                    _share(
                        "e.orcamento_id IS NULL",
                        "LEFT JOIN (SELECT DISTINCT orcamento_id FROM comercial.orcamento_etapa) e "
                        "ON e.orcamento_id = o.id",
                        f"{VENDA} AND o.fase_id = 6 AND o.dt_cadastro <= DATEADD(day, -60, {T})",
                    ),
                ),
                bandas.SHARE_GANHO_SEM_ETAPAS,
                "{:.3f}",
            )
        )
        # --- integridade de negócio ---
        r.append(
            _avaliar(
                "bruto ≠ soma dos itens (share)",
                _num(
                    conn,
                    _share(
                        "ABS(o.vl_total_bruto - ISNULL(i.soma, 0)) > 0.05",
                        "LEFT JOIN (SELECT orcamento_id, SUM(vl_total) AS soma "
                        "FROM comercial.orcamento_item WHERE dt_cancelou IS NULL "
                        "GROUP BY orcamento_id) i ON i.orcamento_id = o.id",
                        "o.dt_cancelou IS NULL",
                    ),
                ),
                bandas.DIVERGENCIA_SOMA_ITENS,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "orçamentos sem nenhum item",
                _num(
                    conn,
                    _share(
                        "i.orcamento_id IS NULL",
                        "LEFT JOIN (SELECT DISTINCT orcamento_id FROM comercial.orcamento_item) i "
                        "ON i.orcamento_id = o.id",
                        "1 = 1",
                    ),
                ),
                bandas.ORCAMENTO_SEM_ITEM,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "ganhos sem recebimento",
                _num(
                    conn,
                    _share(
                        "rc.orcamento_id IS NULL",
                        "LEFT JOIN (SELECT DISTINCT orcamento_id FROM financeiro.recebimento) rc "
                        "ON rc.orcamento_id = o.id",
                        f"{VENDA} AND o.fase_id = 6",
                    ),
                ),
                bandas.GANHO_SEM_RECEBIMENTO,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "ganhos sem comissão apurada (≥ 45 dias)",
                _num(
                    conn,
                    _share(
                        "c.orcamento_id IS NULL",
                        "JOIN comercial.orcamento_fase_hist h "
                        "ON h.orcamento_id = o.id AND h.fase_id = 6 "
                        "LEFT JOIN (SELECT DISTINCT orcamento_id FROM financeiro.comissao) c "
                        "ON c.orcamento_id = o.id",
                        f"{VENDA} AND o.fase_id = 6 AND h.dt_entrada <= DATEADD(day, -45, {T})",
                    ),
                ),
                bandas.GANHO_SEM_COMISSAO,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "fase atual = última fase da trilha",
                _num(
                    conn,
                    _share(
                        "o.fase_id = h.fase_id",
                        "JOIN (SELECT orcamento_id, fase_id, "
                        "ROW_NUMBER() OVER (PARTITION BY orcamento_id "
                        "ORDER BY dt_entrada DESC, id DESC) "
                        "AS rn FROM comercial.orcamento_fase_hist) h "
                        "ON h.orcamento_id = o.id AND h.rn = 1",
                        "1 = 1",
                    ),
                ),
                bandas.FASE_ATUAL_COERENTE_COM_TRILHA,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "fechamento coerente com a fase",
                _num(
                    conn,
                    _share(
                        "(o.fase_id IN (6, 7) AND o.dt_finalizou IS NOT NULL) "
                        "OR (o.fase_id NOT IN (6, 7) AND o.dt_finalizou IS NULL)",
                        "",
                        "o.dt_cancelou IS NULL",
                    ),
                ),
                bandas.FECHAMENTO_COERENTE_COM_FASE,
                "{:.4f}",
            )
        )
    finally:
        conn.close()
    return r


def main() -> None:
    p = argparse.ArgumentParser(description="Régua de validação da origem sintética Fictoria.")
    p.add_argument(
        "--staging", action="store_true", help="valida o staging (espelho) em vez da origem"
    )
    args = p.parse_args()
    alvo = "staging" if args.staging else "origem"
    resultados = executar(conexao_staging() if args.staging else conexao_origem())
    largura = max(len(x.check) for x in resultados)
    reprovados = 0
    print(f"\nRégua de validação da {alvo} — {len(resultados)} checks\n")
    for res in resultados:
        veredito = "OK   " if res.ok else "FALHA"
        if not res.ok:
            reprovados += 1
        print(f"  {veredito}  {res.check.ljust(largura)}  {res.observado:>12}  {res.banda}")
    print(f"\n{len(resultados) - reprovados} aprovados, {reprovados} reprovados.")
    if reprovados:
        print("Veredito: REGENERAR a base (banda estourada não se contorna).")
        sys.exit(1)
    print(f"Veredito: {alvo} APROVADA pela régua.")


if __name__ == "__main__":
    main()
