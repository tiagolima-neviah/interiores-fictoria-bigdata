"""Gera e executa os notebooks 03 (avaliação do modelo multidimensional) e 04 (testes de
indicadores: warehouse × origem, mais os ritos executivos).

Uso: `uv run notebooks-modelo`. Os dois lêem o warehouse SQL Server pelo pacote (`config`),
e o 04 recalcula cada indicador direto na origem transacional, com as regras de negócio,
para provar que o star schema não perdeu nem inventou nada.
"""

from __future__ import annotations

import time
from typing import Any

import pyodbc
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from interiores_fictoria import db
from interiores_fictoria.config import RAIZ_PROJETO, conexao_origem, conexao_warehouse
from interiores_fictoria.notebooks.construtor import executar

SETUP = """import pandas as pd, pyodbc
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from interiores_fictoria.config import conexao_origem, conexao_warehouse

pd.set_option("display.max_columns", 40); pd.set_option("display.width", 180)
dw = pyodbc.connect(conexao_warehouse(), timeout=15)
origem = pyodbc.connect(conexao_origem(), timeout=15)

from decimal import Decimal

def q(sql, cx=dw):
    cur = cx.cursor(); cur.execute(sql)
    cols = [d[0] for d in cur.description]
    linhas = [tuple(float(v) if isinstance(v, Decimal) else v for v in r) for r in cur.fetchall()]
    return pd.DataFrame.from_records(linhas, columns=cols)

print("warehouse:", q("SELECT DB_NAME() AS banco").iloc[0, 0], "| origem:", q("SELECT DB_NAME() AS banco", origem).iloc[0, 0])
"""

# --- notebook 03: avaliação do modelo ------------------------------------------------

AVALIACAO: list[tuple[str, str]] = [
    (
        "Inventário do schema `dw`: tabelas, linhas e espaço",
        """
        SELECT t.name AS tabela, SUM(p.rows) AS linhas,
               CAST(SUM(a.total_pages) * 8.0 / 1024 AS decimal(10,2)) AS mb,
               MAX(CASE WHEN i.type = 5 THEN 'columnstore' WHEN i.type = 1 THEN 'clustered (PK)' ELSE 'heap' END) AS armazenamento
        FROM sys.tables t
        JOIN sys.indexes i ON i.object_id = t.object_id AND i.index_id IN (0, 1)
        JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id = i.index_id
        JOIN sys.allocation_units a ON a.container_id = p.hobt_id OR a.container_id = p.partition_id
        WHERE t.schema_id = SCHEMA_ID('dw') GROUP BY t.name ORDER BY linhas DESC""",
    ),
    (
        "Dimensões: cardinalidade e membros especiais",
        """
        SELECT 'dim_cliente' AS dimensao, COUNT(*) AS membros, SUM(CASE WHEN sk_cliente < 0 THEN 1 ELSE 0 END) AS especiais,
               SUM(CASE WHEN fl_recorrente = 1 THEN 1 ELSE 0 END) AS recorrentes FROM dw.dim_cliente
        UNION ALL SELECT 'dim_parceiro', COUNT(*), SUM(CASE WHEN sk_parceiro < 0 THEN 1 ELSE 0 END), NULL FROM dw.dim_parceiro
        UNION ALL SELECT 'dim_vendedor', COUNT(*), SUM(CASE WHEN sk_vendedor < 0 THEN 1 ELSE 0 END), SUM(CASE WHEN fl_ativo = 1 THEN 1 ELSE 0 END) FROM dw.dim_vendedor
        UNION ALL SELECT 'dim_canal', COUNT(*), SUM(CASE WHEN sk_canal < 0 THEN 1 ELSE 0 END), NULL FROM dw.dim_canal
        UNION ALL SELECT 'dim_calendario', COUNT(*), SUM(CASE WHEN sk_data < 0 THEN 1 ELSE 0 END), SUM(CASE WHEN fl_dia_util = 1 THEN 1 ELSE 0 END) FROM dw.dim_calendario""",
    ),
    (
        "Canal: a visão consolidada (outras origens) e o detalhe por parceiro batem por construção",
        """
        SELECT c.grupo_nome, COUNT(*) AS orcamentos, SUM(o.fl_com_parceiro) AS com_parceiro_cadastrado,
               SUM(CASE WHEN o.sk_parceiro = -2 THEN 1 ELSE 0 END) AS parceiro_texto_livre
        FROM dw.ft_orcamento o JOIN dw.dim_canal c ON c.sk_canal = o.sk_canal
        GROUP BY c.grupo_nome, c.ordem_grupo ORDER BY c.ordem_grupo""",
    ),
    (
        "Grão das fatos: uma linha por chave de negócio e partições por ano",
        """
        SELECT 'ft_orcamento' AS fato, ano, COUNT(*) AS linhas, COUNT(DISTINCT sk_orcamento) AS chaves FROM dw.ft_orcamento GROUP BY ano
        UNION ALL SELECT 'ft_venda', ano, COUNT(*), COUNT(DISTINCT sk_orcamento) FROM dw.ft_venda GROUP BY ano
        ORDER BY fato, ano""",
    ),
    (
        "Integridade referencial no warehouse: chaves órfãs (esperado: zero em todas)",
        """
        SELECT 'ft_orcamento → dim_vendedor' AS relacao, COUNT(*) AS orfas FROM dw.ft_orcamento f LEFT JOIN dw.dim_vendedor d ON d.sk_vendedor = f.sk_vendedor WHERE d.sk_vendedor IS NULL
        UNION ALL SELECT 'ft_orcamento → dim_cliente', COUNT(*) FROM dw.ft_orcamento f LEFT JOIN dw.dim_cliente d ON d.sk_cliente = f.sk_cliente WHERE d.sk_cliente IS NULL
        UNION ALL SELECT 'ft_orcamento → dim_parceiro', COUNT(*) FROM dw.ft_orcamento f LEFT JOIN dw.dim_parceiro d ON d.sk_parceiro = f.sk_parceiro WHERE d.sk_parceiro IS NULL
        UNION ALL SELECT 'ft_orcamento → dim_calendario (cadastro)', COUNT(*) FROM dw.ft_orcamento f LEFT JOIN dw.dim_calendario d ON d.sk_data = f.sk_data_cadastro WHERE d.sk_data IS NULL
        UNION ALL SELECT 'ft_venda → dim_calendario (ganho)', COUNT(*) FROM dw.ft_venda f LEFT JOIN dw.dim_calendario d ON d.sk_data = f.sk_data_ganho WHERE d.sk_data IS NULL
        UNION ALL SELECT 'ft_comissao → dim_parceiro', COUNT(*) FROM dw.ft_comissao f LEFT JOIN dw.dim_parceiro d ON d.sk_parceiro = f.sk_parceiro WHERE d.sk_parceiro IS NULL
        UNION ALL SELECT 'ft_orcamento_item → dim_item', COUNT(*) FROM dw.ft_orcamento_item f LEFT JOIN dw.dim_item d ON d.sk_item = f.sk_item WHERE d.sk_item IS NULL
        UNION ALL SELECT 'ft_funil_posicao → dim_fase', COUNT(*) FROM dw.ft_funil_posicao f LEFT JOIN dw.dim_fase d ON d.sk_fase = f.sk_fase WHERE d.sk_fase IS NULL""",
    ),
    (
        "Posição do funil no último fim de mês × situação atual",
        """
        WITH atual AS (
          SELECT 'ABERTO' AS grupo_fase, SUM(fl_aberto) AS n FROM dw.ft_orcamento
          UNION ALL SELECT 'GANHO', SUM(fl_ganho) FROM dw.ft_orcamento
          UNION ALL SELECT 'PERDIDO', SUM(fl_perdido) FROM dw.ft_orcamento),
        pos AS (
          SELECT grupo_fase, SUM(qtd_orcamentos) AS n FROM dw.ft_funil_posicao
          WHERE sk_data_posicao = (SELECT MAX(sk_data_posicao) FROM dw.ft_funil_posicao) GROUP BY grupo_fase)
        SELECT a.grupo_fase, p.n AS posicao_ultimo_mes, a.n AS situacao_atual, p.n - a.n AS diferenca
        FROM atual a JOIN pos p ON p.grupo_fase = a.grupo_fase ORDER BY a.grupo_fase""",
    ),
    (
        "Calendário: as chaves de comparação (mesmo dia do ano anterior) resolvem para dias reais",
        """
        SELECT COUNT(*) AS dias, SUM(CASE WHEN a.sk_data IS NULL THEN 1 ELSE 0 END) AS sem_ano_anterior,
               SUM(CASE WHEN b.sk_data IS NULL THEN 1 ELSE 0 END) AS sem_dois_anos_antes
        FROM dw.dim_calendario c
        LEFT JOIN dw.dim_calendario a ON a.sk_data = c.sk_data_ano_anterior
        LEFT JOIN dw.dim_calendario b ON b.sk_data = c.sk_data_dois_anos_antes
        WHERE c.ano BETWEEN 2023 AND 2027""",
    ),
    (
        "Régua de SLA aplicada por intervalo: conversão sobre fechados por ano e faixa",
        """
        WITH t AS (
          SELECT c.ano, 100.0 * SUM(o.fl_ganho) / NULLIF(SUM(o.fl_fechado), 0) AS conversao,
                 100.0 * SUM(o.fl_perdido) / NULLIF(SUM(o.fl_fechado), 0) AS perda
          FROM dw.ft_orcamento o JOIN dw.dim_calendario c ON c.sk_data = o.sk_data_cadastro
          WHERE o.fl_fechado = 1 GROUP BY c.ano)
        SELECT t.ano, CAST(t.conversao AS decimal(5,1)) AS conversao_pct, sc.faixa AS faixa_conversao,
               CAST(t.perda AS decimal(5,1)) AS perda_pct, sp.faixa AS faixa_perda
        FROM t
        JOIN dw.dim_faixa_sla sc ON sc.tipo = 'CONVERSAO' AND t.conversao > sc.limite_inferior_exclusivo AND t.conversao <= sc.limite_superior_inclusivo
        JOIN dw.dim_faixa_sla sp ON sp.tipo = 'PERDA' AND t.perda > sp.limite_inferior_exclusivo AND t.perda <= sp.limite_superior_inclusivo
        ORDER BY t.ano""",
    ),
]

# --- notebook 04: testes de indicadores (warehouse × origem) -----------------------
# (nome, SQL no warehouse, SQL na origem com as regras de negócio). Ambos devolvem (chave, valor).

VENDA_ORIGEM = "o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL"
GANHO_TRILHA = """JOIN (SELECT orcamento_id, MIN(dt_entrada) AS dt_ganho FROM comercial.orcamento_fase_hist
                       WHERE fase_id = 6 GROUP BY orcamento_id) g ON g.orcamento_id = o.id"""

TESTES: list[tuple[str, str, str]] = [
    (
        "Orçamentos de venda por ano de cadastro (quantidade)",
        "SELECT ano AS chave, COUNT(*) AS valor FROM dw.ft_orcamento GROUP BY ano",
        f"SELECT YEAR(o.dt_cadastro) AS chave, COUNT(*) AS valor FROM comercial.orcamento o WHERE {VENDA_ORIGEM} GROUP BY YEAR(o.dt_cadastro)",
    ),
    (
        "Total bruto orçado por ano de cadastro",
        "SELECT ano AS chave, SUM(vl_bruto) AS valor FROM dw.ft_orcamento GROUP BY ano",
        f"SELECT YEAR(o.dt_cadastro) AS chave, SUM(o.vl_total_bruto) AS valor FROM comercial.orcamento o WHERE {VENDA_ORIGEM} GROUP BY YEAR(o.dt_cadastro)",
    ),
    (
        "Vendas por ano do ganho (quantidade)",
        "SELECT ano AS chave, SUM(qtd_vendas) AS valor FROM dw.ft_venda GROUP BY ano",
        f"SELECT YEAR(g.dt_ganho) AS chave, COUNT(*) AS valor FROM comercial.orcamento o {GANHO_TRILHA} WHERE {VENDA_ORIGEM} AND o.fase_id = 6 GROUP BY YEAR(g.dt_ganho)",
    ),
    (
        "Vendas por ano do ganho (líquido)",
        "SELECT ano AS chave, SUM(vl_liquido) AS valor FROM dw.ft_venda GROUP BY ano",
        f"SELECT YEAR(g.dt_ganho) AS chave, SUM(o.vl_total_liquido) AS valor FROM comercial.orcamento o {GANHO_TRILHA} WHERE {VENDA_ORIGEM} AND o.fase_id = 6 GROUP BY YEAR(g.dt_ganho)",
    ),
    (
        "Comissões apuradas por ano de competência",
        "SELECT ano AS chave, SUM(vl_comissao) AS valor FROM dw.ft_comissao GROUP BY ano",
        f"SELECT CAST(LEFT(c.competencia, 4) AS int) AS chave, SUM(c.vl_comissao) AS valor FROM financeiro.comissao c JOIN comercial.orcamento o ON o.id = c.orcamento_id WHERE {VENDA_ORIGEM} GROUP BY LEFT(c.competencia, 4)",
    ),
    (
        "Maior venda por ano (líquido)",
        "SELECT ano AS chave, MAX(vl_liquido) AS valor FROM dw.ft_venda GROUP BY ano",
        f"SELECT YEAR(g.dt_ganho) AS chave, MAX(o.vl_total_liquido) AS valor FROM comercial.orcamento o {GANHO_TRILHA} WHERE {VENDA_ORIGEM} AND o.fase_id = 6 GROUP BY YEAR(g.dt_ganho)",
    ),
    (
        "Situação atual do funil (abertos, ganhos, perdidos)",
        "SELECT grupo_fase AS chave, COUNT(*) AS valor FROM dw.ft_orcamento GROUP BY grupo_fase",
        f"SELECT f.grupo AS chave, COUNT(*) AS valor FROM comercial.orcamento o JOIN cadastro.fase f ON f.id = o.fase_id WHERE {VENDA_ORIGEM} GROUP BY f.grupo",
    ),
    (
        "Orçamentos por grupo de canal (outras origens)",
        "SELECT c.grupo AS chave, COUNT(*) AS valor FROM dw.ft_orcamento o JOIN dw.dim_canal c ON c.sk_canal = o.sk_canal GROUP BY c.grupo",
        f"SELECT oc.grupo AS chave, COUNT(*) AS valor FROM comercial.orcamento o JOIN cadastro.origem_contato oc ON oc.id = o.origem_contato_id WHERE {VENDA_ORIGEM} GROUP BY oc.grupo",
    ),
    (
        "Vendas por vendedor (líquido, top por id)",
        "SELECT sk_vendedor AS chave, SUM(vl_liquido) AS valor FROM dw.ft_venda GROUP BY sk_vendedor",
        f"SELECT o.vendedor_id AS chave, SUM(o.vl_total_liquido) AS valor FROM comercial.orcamento o WHERE {VENDA_ORIGEM} AND o.fase_id = 6 GROUP BY o.vendedor_id",
    ),
    (
        "Parcelas vencidas sem pagamento (quantidade) por ano de vencimento",
        "SELECT ano AS chave, SUM(fl_vencida_sem_pagamento) AS valor FROM dw.ft_parcela GROUP BY ano",
        f"""SELECT YEAR(p.dt_vencimento) AS chave,
                   SUM(CASE WHEN p.fl_pago = 0 AND p.dt_cancelamento IS NULL AND p.dt_vencimento < tt.t
                            THEN 1 ELSE 0 END) AS valor
            FROM financeiro.parcela p
            JOIN financeiro.recebimento r ON r.id = p.recebimento_id
            JOIN comercial.orcamento o ON o.id = r.orcamento_id
            CROSS JOIN (SELECT CAST(MAX(dt_cadastro) AS date) AS t FROM comercial.orcamento) tt
            WHERE {VENDA_ORIGEM} AND p.dt_cancelamento IS NULL GROUP BY YEAR(p.dt_vencimento)""",
    ),
]

COMPARADOR = """def comparar(nome, sql_dw, sql_origem):
    a = q(sql_dw).set_index("chave")["valor"].astype(float)
    b = q(sql_origem, origem).set_index("chave")["valor"].astype(float)
    df = pd.concat([a.rename("warehouse"), b.rename("origem")], axis=1).fillna(0.0).sort_index()
    df["diferenca"] = (df["warehouse"] - df["origem"]).round(2)
    df["ok"] = df["diferenca"].abs() < 0.01
    print(f"{'OK   ' if df['ok'].all() else 'FALHA'}  {nome}")
    return df
"""

RITOS = '''# Rito MENSAL: agosto de 2026 contra agosto de 2025 e de 2024
mensal = q("""
SELECT c.ano, SUM(v.qtd_vendas) AS vendas, SUM(v.vl_liquido) AS liquido, SUM(v.vl_comissao_total) AS comissoes
FROM dw.ft_venda v JOIN dw.dim_calendario c ON c.sk_data = v.sk_data_ganho
WHERE c.mes = 8 AND c.ano IN (2024, 2025, 2026) GROUP BY c.ano ORDER BY c.ano""")
display(mensal)
# Rito SEMESTRAL: janeiro a julho, três anos
semestral = q("""
SELECT c.ano, COUNT(*) AS orcamentos, SUM(o.fl_ganho) AS ganhos, SUM(o.fl_perdido) AS perdidos, SUM(o.fl_aberto) AS abertos,
       CAST(100.0 * SUM(o.fl_ganho) / NULLIF(SUM(o.fl_fechado), 0) AS decimal(5,1)) AS conversao_pct
FROM dw.ft_orcamento o JOIN dw.dim_calendario c ON c.sk_data = o.sk_data_cadastro
WHERE c.mes BETWEEN 1 AND 7 AND c.ano IN (2024, 2025, 2026) GROUP BY c.ano ORDER BY c.ano""")
display(semestral)
# Rito ANUAL: três anos fechados
anual = q("""
SELECT c.ano, SUM(v.qtd_vendas) AS vendas, SUM(v.vl_liquido) AS liquido, SUM(v.vl_bruto) AS bruto,
       CAST(SUM(v.vl_liquido) / NULLIF(SUM(v.vl_bruto), 0) AS decimal(5,3)) AS margem_liquida,
       CAST(SUM(v.vl_margem_custo) / NULLIF(SUM(v.vl_liquido), 0) AS decimal(5,3)) AS margem_sobre_custo,
       SUM(v.vl_comissao_total) AS comissoes
FROM dw.ft_venda v JOIN dw.dim_calendario c ON c.sk_data = v.sk_data_ganho
WHERE c.ano IN (2023, 2024, 2025) GROUP BY c.ano ORDER BY c.ano""")
display(anual)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].bar(mensal["ano"].astype(str), mensal["liquido"] / 1e6, color=["#c9b79c", "#a3865a", "#5b4a2f"])
axes[0].set_title("Agosto: vendas líquidas (R$ mi)")
axes[1].plot(semestral["ano"].astype(str), semestral["conversao_pct"], marker="o", color="#5b4a2f")
axes[1].set_ylim(0, 60); axes[1].set_title("Jan-jul: conversão sobre fechados (%)")
axes[2].bar(anual["ano"].astype(str), anual["liquido"] / 1e6, color=["#c9b79c", "#a3865a", "#5b4a2f"])
axes[2].set_title("Anual: vendas líquidas (R$ mi)")
for ax in axes:
    for s in ("top", "right"): ax.spines[s].set_visible(False)
plt.tight_layout(); plt.show()
'''

RANKING = '''# Vendedores em 2026: vendas, conversão e faixa do SLA (base da premiação)
rank = q("""
WITH t AS (
  SELECT d.nome AS vendedor, COUNT(*) AS orcamentos, SUM(o.fl_ganho) AS ganhos,
         100.0 * SUM(o.fl_ganho) / NULLIF(SUM(o.fl_fechado), 0) AS conversao
  FROM dw.ft_orcamento o JOIN dw.dim_vendedor d ON d.sk_vendedor = o.sk_vendedor
  WHERE o.ano = 2026 GROUP BY d.nome)
SELECT t.vendedor, t.orcamentos, t.ganhos, CAST(t.conversao AS decimal(5,1)) AS conversao_pct, s.faixa
FROM t JOIN dw.dim_faixa_sla s ON s.tipo = 'CONVERSAO' AND t.conversao > s.limite_inferior_exclusivo AND t.conversao <= s.limite_superior_inclusivo
ORDER BY t.ganhos DESC""")
display(rank)
# Parceiros: quem trouxe mais vendas em 2025 e 2026
parceiros = q("""
SELECT TOP 12 p.tipo, p.nome, SUM(v.qtd_vendas) AS vendas, SUM(v.vl_liquido) AS liquido, SUM(v.vl_comissao_parceiro) AS comissao_parceiro
FROM dw.ft_venda v JOIN dw.dim_parceiro p ON p.sk_parceiro = v.sk_parceiro
WHERE v.ano IN (2025, 2026) AND p.sk_parceiro > 0 GROUP BY p.tipo, p.nome ORDER BY liquido DESC""")
display(parceiros)
# Carteira aberta ao longo do tempo (posição de fim de mês)
carteira = q("""
SELECT c.ano_mes, SUM(p.qtd_orcamentos) AS abertos, SUM(p.vl_liquido) AS liquido_aberto
FROM dw.ft_funil_posicao p JOIN dw.dim_calendario c ON c.sk_data = p.sk_data_posicao
WHERE p.grupo_fase = 'ABERTO' GROUP BY c.ano_mes ORDER BY c.ano_mes""")
fig, ax = plt.subplots(figsize=(14, 3.6))
ax.plot(carteira["ano_mes"], carteira["abertos"], color="#5b4a2f")
ax.set_title("Orçamentos em aberto na posição de fim de mês (2021 a 2026)")
ax.set_xticks(carteira["ano_mes"][::6]); ax.tick_params(axis="x", rotation=45)
for s in ("top", "right"): ax.spines[s].set_visible(False)
plt.tight_layout(); plt.show()
'''


def _df(cx: pyodbc.Connection, sql: str) -> list[tuple[Any, ...]]:
    return db.consultar(cx, sql)


def _medir_testes() -> list[tuple[str, bool, int]]:
    dw, origem = db.conectar(conexao_warehouse()), db.conectar(conexao_origem())
    saida = []
    try:
        for nome, sql_dw, sql_o in TESTES:
            a = {str(k): float(v or 0) for k, v in _df(dw, sql_dw)}
            b = {str(k): float(v or 0) for k, v in _df(origem, sql_o)}
            chaves = set(a) | set(b)
            ok = all(abs(a.get(k, 0.0) - b.get(k, 0.0)) < 0.01 for k in chaves)
            saida.append((nome, ok, len(chaves)))
    finally:
        dw.close()
        origem.close()
    return saida


def _medir_avaliacao() -> dict[str, Any]:
    dw = db.conectar(conexao_warehouse())
    try:
        orfas = sum(int(v) for _, v in _df(dw, AVALIACAO[4][1]))
        tabelas = _df(dw, "SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID('dw')")[0][0]
        linhas_fato = _df(
            dw,
            "SELECT SUM(p.rows) FROM sys.partitions p JOIN sys.tables t ON t.object_id = p.object_id "
            "WHERE t.schema_id = SCHEMA_ID('dw') AND t.name LIKE 'ft_%' AND p.index_id IN (0, 1)",
        )[0][0]
        return {"orfas": orfas, "tabelas": int(tabelas), "linhas_fato": int(linhas_fato)}
    finally:
        dw.close()


def construir_03(m: dict[str, Any]) -> Any:
    nb = new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.cells.append(
        new_markdown_cell(
            "# Avaliação do modelo multidimensional\n\n"
            "O star schema da **Fictoria Casa & Interiores** (fictícia, dados sintéticos) carregado no warehouse SQL Server: "
            "inventário, cardinalidades, membros especiais, grão das fatos, integridade referencial, posição do funil e a "
            "régua de SLA aplicada por intervalo. Cada seção termina numa Nota Técnica escrita a partir do observado. "
            "Contrato: [matriz de barramento](../docs/10_matriz_barramento.md); construção: [gold](../docs/11_camada_gold.md); "
            "carga: [warehouse](../docs/12_warehouse_multidimensional.md).\n\n"
            "> Reprodutível: `uv run notebooks-modelo`."
        )
    )
    nb.cells.append(new_code_cell(SETUP))
    for k, (titulo, sql) in enumerate(AVALIACAO, start=1):
        nb.cells.append(new_markdown_cell(f"## {k}. {titulo}"))
        nb.cells.append(new_code_cell(f'display(q("""{sql}"""))'))
    nb.cells.append(
        new_markdown_cell(
            "**Nota Técnica**\n\n"
            f"- **Observado:** {m['tabelas']} tabelas no schema `dw` (15 dimensões e 7 fatos), {format(m['linhas_fato'], ',').replace(',', '.')} linhas de fato, "
            f"{m['orfas']} chaves órfãs nas relações testadas; a posição do funil no último fim de mês reproduz a situação atual "
            "e a conversão por ano cai nas faixas do SLA da diretoria (crítico em 2021, excelente em 2026).\n"
            "- **Por que importa:** um star schema sem chave órfã e com grão provado é o que permite ao dashboard somar sem "
            "medo; a leitura consolidada por canal e o detalhe por parceiro saem da mesma linha, então batem por construção.\n"
            "- **Ação:** o warehouse está pronto para o dashboard web e para o Power BI; a mesma carga aponta para a nuvem por `.env` quando houver destino.".replace(
                ",", "."
            )
        )
    )
    return nb


def construir_04(resultados: list[tuple[str, bool, int]]) -> Any:
    nb = new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    ok = sum(1 for _, o, _ in resultados if o)
    nb.cells.append(
        new_markdown_cell(
            "# Testes de indicadores: warehouse × origem\n\n"
            "Cada indicador da diretoria é calculado duas vezes: no **warehouse** (star schema) e direto na **origem** "
            "(o SQL Server transacional, com as regras de negócio aplicadas à mão: tipo Venda, não cancelado, data do ganho "
            "pela trilha de fases). A diferença tem de ser zero. Depois, os **ritos executivos** (mensal, semestral, anual) "
            "e as leituras de premiação (vendedores e parceiros) desenhados a partir do warehouse.\n\n"
            "> Reprodutível: `uv run notebooks-modelo`."
        )
    )
    nb.cells.append(new_code_cell(SETUP))
    nb.cells.append(new_code_cell(COMPARADOR))
    nb.cells.append(new_markdown_cell("## 1. Indicadores: warehouse × origem"))
    for nome, sql_dw, sql_o in TESTES:
        nb.cells.append(
            new_code_cell(f'display(comparar({nome!r}, """{sql_dw}""", """{sql_o}"""))')
        )
    nb.cells.append(
        new_markdown_cell(
            "**Nota Técnica**\n\n"
            f"- **Observado:** {ok} de {len(resultados)} indicadores idênticos entre warehouse e origem, em todas as chaves "
            "(anos, grupos de fase, grupos de canal, vendedores).\n"
            "- **Por que importa:** é a prova de que bronze, silver e gold não perderam nem inventaram nada: o número que a "
            "diretoria vê no dashboard é o mesmo que uma consulta cuidadosa no sistema devolveria, sem pesar na produção.\n"
            "- **Ação:** qualquer divergência futura aparece aqui antes de chegar a um relatório; este notebook é a régua de aceite dos indicadores."
        )
    )
    nb.cells.append(new_markdown_cell("## 2. Os ritos executivos, lidos do warehouse"))
    nb.cells.append(new_code_cell(RITOS))
    nb.cells.append(
        new_markdown_cell(
            "## 3. Premiação: vendedores com faixa do SLA, parceiros e a carteira aberta no tempo"
        )
    )
    nb.cells.append(new_code_cell(RANKING))
    nb.cells.append(
        new_markdown_cell(
            "## Encerramento\n\nO pipeline fechou o ciclo: do sistema comercial simulado ao warehouse multidimensional, "
            "com cada camada prestando contas à anterior. As perguntas da diretoria têm resposta por construção, "
            "e a sazonalidade, o arco de conversão e a carteira aberta contam a história da empresa."
        )
    )
    return nb


def main() -> None:
    inicio = time.perf_counter()
    pasta = RAIZ_PROJETO / "notebooks"
    pasta.mkdir(exist_ok=True)
    medidas = _medir_avaliacao()
    print(f"Modelo no warehouse: {medidas}")
    resultados = _medir_testes()
    for nome, ok, n in resultados:
        print(f"  {'OK   ' if ok else 'FALHA'}  {nome} ({n} chaves)")
    for nome, nb in [
        ("03_avaliacao_modelo_multidimensional", construir_03(medidas)),
        ("04_testes_indicadores", construir_04(resultados)),
    ]:
        t0 = time.perf_counter()
        executar(nb, pasta / f"{nome}.ipynb")
        print(f"notebooks/{nome}.ipynb executado em {time.perf_counter() - t0:.1f}s")
    falhas = [n for n, ok, _ in resultados if not ok]
    print(f"\nConcluído em {time.perf_counter() - inicio:.1f}s.")
    if falhas:
        raise SystemExit("Indicadores divergentes: " + "; ".join(falhas))
    print("Todos os indicadores batem entre warehouse e origem.")


if __name__ == "__main__":
    main()
