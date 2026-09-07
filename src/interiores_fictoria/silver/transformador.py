"""Silver: estado corrente por chave + regras do catálogo de achados + prestação de contas.

Uso: `uv run silver-staging`. Lê o bronze (todas as cargas; a chave fica com o maior
`_rv_origem`), aplica as regras ACH-01..16 documentadas em `docs/08` e grava uma pasta por
tabela em `silver/<tabela>/parte-000.parquet`. Ao final presta contas: para cada regra,
quantas linhas foram afetadas, e um conjunto de conferências que reprova a execução
(código de saída 1) se a silver não bater com o bronze. Ausência não se preenche: flags
marcam, nunca inventam.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import duckdb

from interiores_fictoria import duck
from interiores_fictoria.lake import Lake, novo_manifesto

# Data corrente do universo: o último cadastro (não o relógio da máquina).
T = "(SELECT MAX(dt_cadastro) FROM b_orcamento)"

# Tabelas que passam sem transformação além da deduplicação por chave.
PASSAGEM = (
    "unidade",
    "usuario",
    "origem_contato",
    "parceiro",
    "tipo_orcamento",
    "fase",
    "motivo_perda",
    "status_etapa",
    "ambiente",
    "categoria_item",
    "fornecedor",
    "item_catalogo",
    "forma_pagamento",
    "condicao_parcelamento",
    "follow_up",
    "orcamento_historico",
    "recebimento",
    "pagamento",
    "medicao",
    "instalacao",
    "instalacao_historico",
    "orcamento_fase_hist",
)

TRANSFORMACOES: dict[str, str] = {
    "cliente": """
        WITH n AS (
          SELECT *, regexp_replace(strip_accents(lower(trim(nome))), '\\s+', ' ', 'g') AS nome_normalizado
          FROM b_cliente),
        canonico AS (SELECT nome_normalizado, MIN(id) AS cliente_canonico_id FROM n GROUP BY 1),
        principal AS (
          SELECT cliente_id, bairro, cidade, uf, cep,
                 row_number() OVER (PARTITION BY cliente_id ORDER BY fl_principal DESC, id) AS rn
          FROM b_endereco)
        SELECT n.*, c.cliente_canonico_id,
               (c.cliente_canonico_id <> n.id) AS fl_duplicado_por_grafia,          -- ACH-05
               p.bairro AS bairro_principal, p.cidade AS cidade_principal, p.uf AS uf_principal,
               (p.bairro IS NULL) AS fl_sem_bairro                                    -- ACH-06
        FROM n JOIN canonico c USING (nome_normalizado)
        LEFT JOIN principal p ON p.cliente_id = n.id AND p.rn = 1
    """,
    "endereco": """
        SELECT *, (cep IS NULL) AS fl_sem_cep, (bairro IS NULL) AS fl_sem_bairro    -- ACH-06
        FROM b_endereco
    """,
    "orcamento": """
        WITH fechamento AS (
          SELECT orcamento_id, MIN(dt_entrada) AS dt_fechamento_trilha
          FROM b_orcamento_fase_hist WHERE fase_id IN (6, 7) GROUP BY 1),
        itens AS (
          SELECT orcamento_id,
                 SUM(CASE WHEN dt_cancelou IS NULL THEN vl_total ELSE 0 END) AS vl_bruto_itens,
                 SUM(CASE WHEN dt_cancelou IS NULL THEN COALESCE(vl_custo, 0) ELSE 0 END) AS vl_custo_itens,
                 SUM(CASE WHEN dt_cancelou IS NULL THEN 1 ELSE 0 END) AS qtd_itens
          FROM b_orcamento_item GROUP BY 1),
        fups AS (SELECT orcamento_id, COUNT(*) AS qtd_follow_ups FROM b_follow_up GROUP BY 1),
        revisoes AS (
          SELECT orcamento_id, COUNT(*) AS qtd_revisoes FROM b_auditoria_orcamento
          WHERE ds_campo = 'vl_total_liquido' AND vl_novo <> '(criação)' GROUP BY 1),
        etapa_atual AS (
          SELECT e.orcamento_id, s.nome AS status_operacional,
                 row_number() OVER (PARTITION BY e.orcamento_id ORDER BY e.dt_cadastro DESC, e.id DESC) AS rn
          FROM b_orcamento_etapa e JOIN b_status_etapa s ON s.id = e.status_etapa_id
          WHERE e.dt_cancelou IS NULL),
        recebimento AS (SELECT DISTINCT orcamento_id FROM b_recebimento)
        SELECT o.*,
               f.grupo AS grupo_fase,
               (o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL) AS fl_conta_bi,          -- ACH-10
               o.dt_finalizou AS dt_finalizou_registrado,
               (o.dt_finalizou = TIMESTAMP '1900-01-01') AS fl_dt_finalizou_sentinela,        -- ACH-01
               (o.dt_finalizou > TIMESTAMP '1900-01-01' AND o.dt_finalizou < o.dt_cadastro)
                   AS fl_fechou_antes_cadastro,                                                -- ACH-02
               CASE WHEN o.fase_id IN (6, 7) THEN fe.dt_fechamento_trilha END AS dt_fechamento, -- ACH-01/02/11
               CASE WHEN o.fase_id IN (6, 7)
                    THEN date_diff('day', o.dt_cadastro, fe.dt_fechamento_trilha) END AS dias_ate_fechar,
               (o.vl_total_bruto = 0) AS fl_valor_zero,                                        -- ACH-03
               COALESCE(i.vl_bruto_itens, 0) AS vl_bruto_itens,
               COALESCE(i.vl_custo_itens, 0) AS vl_custo_itens,
               COALESCE(i.qtd_itens, 0) AS qtd_itens,
               (ABS(o.vl_total_bruto - COALESCE(i.vl_bruto_itens, 0)) > 0.05) AS fl_divergencia_itens, -- ACH-04
               CASE WHEN o.ds_objetivo LIKE 'Indicação:%'
                    THEN trim(regexp_extract(o.ds_objetivo, 'Indicação: ([^.]+)\\.', 1)) END
                   AS parceiro_texto_livre,                                                    -- ACH-07
               COALESCE(fu.qtd_follow_ups, 0) AS qtd_follow_ups,                               -- ACH-09
               COALESCE(r.qtd_revisoes, 0) AS qtd_revisoes,                                    -- ACH-14
               COALESCE(ea.status_operacional, 'NÃO DEFINIDO') AS status_operacional,          -- ACH-08
               (o.fase_id = 6 AND ea.orcamento_id IS NULL) AS fl_sem_trilha_execucao,
               (o.fase_id = 6 AND rc.orcamento_id IS NULL) AS fl_ganho_sem_recebimento,         -- ACH-15
               o.vl_total_liquido - COALESCE(i.vl_custo_itens, 0) AS vl_margem_custo
        FROM b_orcamento o
        JOIN b_fase f ON f.id = o.fase_id
        LEFT JOIN fechamento fe ON fe.orcamento_id = o.id
        LEFT JOIN itens i ON i.orcamento_id = o.id
        LEFT JOIN fups fu ON fu.orcamento_id = o.id
        LEFT JOIN revisoes r ON r.orcamento_id = o.id
        LEFT JOIN etapa_atual ea ON ea.orcamento_id = o.id AND ea.rn = 1
        LEFT JOIN recebimento rc ON rc.orcamento_id = o.id
    """,
    "orcamento_item": """
        SELECT i.*, (i.dt_cancelou IS NOT NULL) AS fl_cancelado, c.categoria_item_id,
               i.vl_total - COALESCE(i.vl_custo, 0) AS vl_margem_custo
        FROM b_orcamento_item i JOIN b_item_catalogo c ON c.id = i.item_catalogo_id
    """,
    "orcamento_etapa": f"""
        SELECT e.*, s.nome AS status_nome, s.ordem AS status_ordem,
               (e.dt_cancelou IS NULL AND (
                   (e.dt_concluiu IS NOT NULL AND CAST(e.dt_concluiu AS DATE) > e.dt_limite)
                OR (e.dt_concluiu IS NULL AND e.dt_limite < CAST({T} AS DATE)))) AS fl_atrasada
        FROM b_orcamento_etapa e JOIN b_status_etapa s ON s.id = e.status_etapa_id
    """,
    "auditoria_orcamento": """
        SELECT a.*,
               CASE WHEN a.ds_campo IN ('vl_total_liquido', 'vl_desconto', 'vl_total_bruto')
                     AND a.vl_antigo IS NOT NULL AND a.vl_antigo <> '(criação)'
                    THEN TRY_CAST(replace(replace(a.vl_antigo, '.', ''), ',', '.') AS DECIMAL(14, 2)) END
                   AS vl_antigo_num,                                                            -- ACH-14
               CASE WHEN a.ds_campo IN ('vl_total_liquido', 'vl_desconto', 'vl_total_bruto')
                     AND a.vl_novo IS NOT NULL AND a.vl_novo <> '(criação)'
                    THEN TRY_CAST(replace(replace(a.vl_novo, '.', ''), ',', '.') AS DECIMAL(14, 2)) END
                   AS vl_novo_num
        FROM b_auditoria_orcamento a
    """,
    "parcela": f"""
        WITH pg AS (
          SELECT parcela_id, MIN(dt_pagamento) AS dt_primeiro_pagamento, SUM(vl_pago) AS vl_pago_total
          FROM b_pagamento GROUP BY 1)
        SELECT p.*, pg.dt_primeiro_pagamento, pg.vl_pago_total,
               (NOT p.fl_pago AND p.dt_cancelamento IS NULL AND p.dt_vencimento < CAST({T} AS DATE))
                   AS fl_vencida_sem_pagamento,                                                -- ACH-13
               CASE WHEN pg.dt_primeiro_pagamento IS NOT NULL
                    THEN GREATEST(date_diff('day', p.dt_vencimento, pg.dt_primeiro_pagamento), 0) END
                   AS dias_atraso_pagamento
        FROM b_parcela p LEFT JOIN pg ON pg.parcela_id = p.id
    """,
    "comissao": """
        SELECT c.*,
               CASE c.tipo WHEN 'VENDEDOR' THEN o.p_comissao_vendedor
                           WHEN 'PARCEIRO' THEN o.p_comissao_parceiro
                           WHEN '3D' THEN o.p_comissao_3d END AS p_comissao_esperado,
               (c.tipo <> 'SUPERVISOR' AND c.p_comissao <> CASE c.tipo
                    WHEN 'VENDEDOR' THEN o.p_comissao_vendedor
                    WHEN 'PARCEIRO' THEN o.p_comissao_parceiro
                    WHEN '3D' THEN o.p_comissao_3d END) AS fl_comissao_divergente,            -- ACH-12
               c.vl_comissao - c.vl_base * COALESCE(CASE c.tipo
                    WHEN 'VENDEDOR' THEN o.p_comissao_vendedor
                    WHEN 'PARCEIRO' THEN o.p_comissao_parceiro
                    WHEN '3D' THEN o.p_comissao_3d ELSE c.p_comissao END, 0) / 100 AS vl_diferenca_esperado
        FROM b_comissao c JOIN b_orcamento o ON o.id = c.orcamento_id
    """,
}

# Prestação de contas: (achado, descrição, SQL que conta linhas afetadas na silver)
CONTAS: list[tuple[str, str, str]] = [
    (
        "ACH-01",
        "fechamentos com data-sentinela substituída pela trilha",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_dt_finalizou_sentinela",
    ),
    (
        "ACH-02",
        "fechamentos anteriores ao cadastro substituídos pela trilha",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_fechou_antes_cadastro",
    ),
    (
        "ACH-03",
        "orçamentos de valor zero sinalizados",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_valor_zero",
    ),
    (
        "ACH-04",
        "orçamentos com bruto divergente dos itens sinalizados",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_divergencia_itens",
    ),
    (
        "ACH-05",
        "clientes apontados para um cadastro canônico (duplicados por grafia)",
        "SELECT COUNT(*) FROM s_cliente WHERE fl_duplicado_por_grafia",
    ),
    (
        "ACH-06",
        "endereços sem CEP ou sem bairro (preservados como ausência)",
        "SELECT COUNT(*) FROM s_endereco WHERE fl_sem_cep OR fl_sem_bairro",
    ),
    (
        "ACH-07",
        "orçamentos com parceiro em texto livre extraído",
        "SELECT COUNT(*) FROM s_orcamento WHERE parceiro_texto_livre IS NOT NULL",
    ),
    (
        "ACH-08",
        "ganhos sem trilha de execução (status NÃO DEFINIDO)",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_sem_trilha_execucao",
    ),
    (
        "ACH-09",
        "orçamentos de venda sem nenhum follow-up",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_conta_bi AND qtd_follow_ups = 0",
    ),
    (
        "ACH-10",
        "orçamentos fora do escopo do BI (não-venda ou cancelados)",
        "SELECT COUNT(*) FROM s_orcamento WHERE NOT fl_conta_bi",
    ),
    (
        "ACH-12",
        "comissões com percentual divergente do orçamento",
        "SELECT COUNT(*) FROM s_comissao WHERE fl_comissao_divergente",
    ),
    (
        "ACH-13",
        "parcelas vencidas sem pagamento",
        "SELECT COUNT(*) FROM s_parcela WHERE fl_vencida_sem_pagamento",
    ),
    (
        "ACH-14",
        "alterações monetárias da auditoria convertidas para número",
        "SELECT COUNT(*) FROM s_auditoria_orcamento WHERE vl_novo_num IS NOT NULL",
    ),
    (
        "ACH-15",
        "ganhos sem recebimento sinalizados",
        "SELECT COUNT(*) FROM s_orcamento WHERE fl_ganho_sem_recebimento",
    ),
]

# Conferências que reprovam a execução: (nome, SQL que devolve 1 quando OK)
CONFERENCIAS: list[tuple[str, str]] = [
    (
        "silver.orcamento tem uma linha por id",
        "SELECT COUNT(*) = COUNT(DISTINCT id) FROM s_orcamento",
    ),
    (
        "silver.orcamento = bronze (estado corrente) em linhas",
        "SELECT (SELECT COUNT(*) FROM s_orcamento) = (SELECT COUNT(*) FROM b_orcamento)",
    ),
    (
        "silver.orcamento_item = bronze em linhas",
        "SELECT (SELECT COUNT(*) FROM s_orcamento_item) = (SELECT COUNT(*) FROM b_orcamento_item)",
    ),
    (
        "soma do bruto preservada (cabeçalho é a verdade dos valores)",
        "SELECT ABS((SELECT SUM(vl_total_bruto) FROM s_orcamento) - (SELECT SUM(vl_total_bruto) FROM b_orcamento)) < 0.01",
    ),
    (
        "todo fechado tem dt_fechamento pela trilha",
        "SELECT COUNT(*) = 0 FROM s_orcamento WHERE fase_id IN (6, 7) AND dt_fechamento IS NULL",
    ),
    (
        "nenhum aberto tem dt_fechamento",
        "SELECT COUNT(*) = 0 FROM s_orcamento WHERE fase_id NOT IN (6, 7) AND dt_fechamento IS NOT NULL",
    ),
    (
        "dias_ate_fechar nunca negativo (trilha corrige ACH-02)",
        "SELECT COUNT(*) = 0 FROM s_orcamento WHERE dias_ate_fechar < 0",
    ),
    (
        "cliente canônico existe e é o menor id do grupo",
        "SELECT COUNT(*) = 0 FROM s_cliente c LEFT JOIN s_cliente k ON k.id = c.cliente_canonico_id WHERE k.id IS NULL OR k.id > c.id",
    ),
    (
        "fl_conta_bi bate com a regra Venda + não cancelado no bronze",
        "SELECT (SELECT COUNT(*) FROM s_orcamento WHERE fl_conta_bi) = (SELECT COUNT(*) FROM b_orcamento WHERE tipo_orcamento_id = 1 AND dt_cancelou IS NULL)",
    ),
    (
        "comissões: toda linha tem orçamento na silver",
        "SELECT COUNT(*) = 0 FROM s_comissao c LEFT JOIN s_orcamento o ON o.id = c.orcamento_id WHERE o.id IS NULL",
    ),
]


def _gravar(con: duckdb.DuckDBPyConnection, lake: Lake, nome: str, sql: str) -> int:
    destino = lake.caminho("silver", nome, "parte-000.parquet")
    lake.apagar("silver", nome)
    lake.fs.makedirs(lake.caminho("silver", nome), exist_ok=True)
    con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return int(con.execute(f"SELECT COUNT(*) FROM read_parquet('{destino}')").fetchone()[0])  # type: ignore[index]


def main() -> None:
    inicio = time.perf_counter()
    con, lake = duck.conectar()
    manifesto = novo_manifesto("silver")
    print(f"Silver: bronze → {lake.raiz}/silver\n")
    print(f"  {'tabela':28} {'linhas':>9} {'tempo':>7}")
    for nome in PASSAGEM:
        t0 = time.perf_counter()
        n = _gravar(con, lake, nome, f"SELECT * FROM b_{nome}")
        manifesto.registrar(nome, linhas=n, regra="passagem (dedup por chave)")
        print(f"  {nome:28} {n:>9} {time.perf_counter() - t0:>6.1f}s")
    for nome, sql in TRANSFORMACOES.items():
        t0 = time.perf_counter()
        n = _gravar(con, lake, nome, sql)
        manifesto.registrar(nome, linhas=n, regra="transformada")
        print(f"  {nome:28} {n:>9} {time.perf_counter() - t0:>6.1f}s  (regras aplicadas)")
    duck.registrar_silver(con, lake)
    print("\nPrestação de contas (linhas afetadas por regra):")
    contas: dict[str, Any] = {}
    for aid, descricao, sql in CONTAS:
        n = int(con.execute(sql).fetchone()[0])  # type: ignore[index]
        contas[aid] = {"descricao": descricao, "linhas": n}
        print(f"  {aid}  {n:>8}  {descricao}")
    print("\nConferências:")
    reprovadas = []
    for nome, sql in CONFERENCIAS:
        ok = bool(con.execute(sql).fetchone()[0])  # type: ignore[index]
        print(f"  {'OK   ' if ok else 'FALHA'}  {nome}")
        if not ok:
            reprovadas.append(nome)
    dados = manifesto.fechar()
    dados["prestacao_contas"] = contas
    dados["conferencias"] = {n: n not in reprovadas for n, _ in CONFERENCIAS}
    lake.escrever_json(dados, "silver", "_controle", "prestacao_contas.json")
    print(
        f"\nConcluído em {time.perf_counter() - inicio:.1f}s; "
        f"{len(CONFERENCIAS) - len(reprovadas)}/{len(CONFERENCIAS)} conferências aprovadas."
    )
    if reprovadas:
        print("Veredito: silver REPROVADA (a prestação de contas não fechou).")
        sys.exit(1)
    print("Veredito: silver APROVADA. Próximo: uv run gold-staging")


if __name__ == "__main__":
    main()
