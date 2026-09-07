"""O star schema da Fictoria: dimensões conformadas e fatos, em SQL DuckDB sobre a silver.

Convenções: `sk_*` são as chaves substitutas (aqui iguais aos ids da origem quando a
entidade é estável, e `yyyymmdd` para datas); membro `-1` = não informado / não se aplica;
`-2` no parceiro = "Outros / não cadastrado". Fatos carregam flags como 0/1 para somar.
Toda fato tem a coluna `ano` (partição hive) e só entram orçamentos com `fl_conta_bi`.
"""

from __future__ import annotations

T = "(SELECT MAX(dt_cadastro) FROM s_orcamento)"

MACROS = """
CREATE OR REPLACE MACRO sk_data(d) AS COALESCE(CAST(strftime(CAST(d AS DATE), '%Y%m%d') AS INTEGER), -1);
CREATE OR REPLACE MACRO faixa_valor(v) AS CASE
    WHEN v IS NULL OR v <= 0 THEN -1
    WHEN v <= 20000 THEN 1 WHEN v <= 70000 THEN 2 WHEN v <= 200000 THEN 3
    WHEN v <= 400000 THEN 4 ELSE 5 END;
CREATE OR REPLACE MACRO sk_parceiro_de(parceiro_id, texto_livre) AS
    COALESCE(parceiro_id, CASE WHEN texto_livre IS NOT NULL THEN -2 ELSE -1 END);
"""

DIMENSOES: dict[str, str] = {
    "dim_calendario": f"""
        WITH d AS (
          SELECT CAST(unnest(generate_series(DATE '2021-01-01', DATE '2027-12-31', INTERVAL 1 DAY)) AS DATE) AS data),
        c AS (
          SELECT sk_data(data) AS sk_data, data,
                 year(data) AS ano, month(data) AS mes, day(data) AS dia,
                 quarter(data) AS trimestre, CASE WHEN month(data) <= 6 THEN 1 ELSE 2 END AS semestre,
                 weekofyear(data) AS semana_iso, isodow(data) AS dia_semana, dayofyear(data) AS dia_do_ano,
                 CASE isodow(data) WHEN 1 THEN 'Segunda' WHEN 2 THEN 'Terça' WHEN 3 THEN 'Quarta'
                      WHEN 4 THEN 'Quinta' WHEN 5 THEN 'Sexta' WHEN 6 THEN 'Sábado' ELSE 'Domingo' END AS nome_dia,
                 CASE month(data) WHEN 1 THEN 'Janeiro' WHEN 2 THEN 'Fevereiro' WHEN 3 THEN 'Março'
                      WHEN 4 THEN 'Abril' WHEN 5 THEN 'Maio' WHEN 6 THEN 'Junho' WHEN 7 THEN 'Julho'
                      WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Setembro' WHEN 10 THEN 'Outubro'
                      WHEN 11 THEN 'Novembro' ELSE 'Dezembro' END AS nome_mes,
                 CASE month(data) WHEN 1 THEN 'Jan' WHEN 2 THEN 'Fev' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Abr'
                      WHEN 5 THEN 'Mai' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Ago' WHEN 9 THEN 'Set'
                      WHEN 10 THEN 'Out' WHEN 11 THEN 'Nov' ELSE 'Dez' END AS nome_mes_abrev,
                 strftime(data, '%Y-%m') AS ano_mes,
                 year(data) || '-T' || quarter(data) AS ano_trimestre,
                 year(data) || '-S' || CASE WHEN month(data) <= 6 THEN 1 ELSE 2 END AS ano_semestre,
                 year(data) || '-W' || lpad(CAST(weekofyear(data) AS VARCHAR), 2, '0') AS ano_semana,
                 (isodow(data) <= 5) AS fl_dia_util, (isodow(data) >= 6) AS fl_fim_de_semana,
                 sk_data(data - INTERVAL 1 YEAR) AS sk_data_ano_anterior,
                 sk_data(data - INTERVAL 2 YEAR) AS sk_data_dois_anos_antes,
                 (data <= CAST({T} AS DATE)) AS fl_ate_data_corrente,
                 (strftime(data, '%Y-%m') = strftime(CAST({T} AS DATE), '%Y-%m')) AS fl_mes_corrente,
                 (year(data) = year(CAST({T} AS DATE))) AS fl_ano_corrente,
                 (month(data) <= month(CAST({T} AS DATE))
                   AND NOT (month(data) = month(CAST({T} AS DATE)) AND day(data) > day(CAST({T} AS DATE))))
                   AS fl_acumulado_ano_comparavel
          FROM d)
        SELECT * FROM c
        UNION ALL
        SELECT -1, NULL, -1, -1, -1, -1, -1, -1, -1, -1, 'Data inválida', 'Data inválida', 'n/d', 'n/d', 'n/d',
               'n/d', 'n/d', false, false, -1, -1, false, false, false, false
    """,
    "dim_unidade": """
        SELECT id AS sk_unidade, sigla, nome, bairro, cidade, uf, dt_abertura, year(dt_abertura) AS ano_abertura, ativo
        FROM s_unidade
        UNION ALL SELECT -1, 'N/D', 'Não informada', NULL, NULL, NULL, NULL, -1, false
    """,
    "dim_vendedor": """
        SELECT u.id AS sk_vendedor, u.nome, u.login, u.cargo, u.unidade_id AS sk_unidade, un.sigla AS unidade,
               u.dt_admissao, u.dt_desligamento, year(u.dt_admissao) AS ano_admissao,
               (u.dt_desligamento IS NULL) AS fl_ativo
        FROM s_usuario u JOIN s_unidade un ON un.id = u.unidade_id
        WHERE u.cargo IN ('VENDEDOR', 'SUPERVISOR', 'PROJETISTA_3D')
        UNION ALL SELECT -1, 'Não informado', 'n/d', 'N/D', -1, 'N/D', NULL, NULL, -1, false
    """,
    "dim_cliente": """
        WITH primeiro AS (
          SELECT c.cliente_canonico_id, MIN(o.dt_cadastro) AS dt_primeiro_orcamento,
                 COUNT(*) AS qtd_orcamentos_total
          FROM s_orcamento o JOIN s_cliente c ON c.id = o.cliente_id WHERE o.fl_conta_bi GROUP BY 1)
        SELECT c.id AS sk_cliente, c.nome, c.tipo_pessoa,
               CASE c.tipo_pessoa WHEN 'PJ' THEN 'Pessoa jurídica' ELSE 'Pessoa física' END AS tipo_pessoa_nome,
               COALESCE(c.bairro_principal, 'Não informado') AS bairro,
               COALESCE(c.cidade_principal, 'Não informada') AS cidade, COALESCE(c.uf_principal, 'N/D') AS uf,
               COALESCE(oc.grupo, 'N/D') AS grupo_primeiro_contato, COALESCE(oc.nome, 'Não informado') AS canal_primeiro_contato,
               c.unidade_id AS sk_unidade_origem, year(c.dt_cadastro) AS ano_cadastro, c.dt_cadastro,
               (c.cliente_indicador_id IS NOT NULL) AS fl_indicado_por_cliente,
               (c.parceiro_indicador_id IS NOT NULL) AS fl_indicado_por_parceiro,
               COALESCE(p.qtd_orcamentos_total, 0) AS qtd_orcamentos_total,
               (COALESCE(p.qtd_orcamentos_total, 0) > 1) AS fl_recorrente,
               (SELECT COUNT(*) FROM s_cliente d WHERE d.cliente_canonico_id = c.id) AS qtd_cadastros_agrupados
        FROM s_cliente c
        LEFT JOIN s_origem_contato oc ON oc.id = c.origem_contato_id
        LEFT JOIN primeiro p ON p.cliente_canonico_id = c.id
        WHERE c.id = c.cliente_canonico_id
        UNION ALL SELECT -1, 'Não informado', 'N/D', 'N/D', 'Não informado', 'Não informada', 'N/D', 'N/D',
                         'Não informado', -1, -1, NULL, false, false, 0, false, 0
    """,
    "dim_canal": """
        SELECT id AS sk_canal, codigo, nome, grupo,
               CASE grupo WHEN 'ARQUITETOS' THEN 'Arquitetos' WHEN 'CONSTRUTORAS' THEN 'Construtoras'
                    WHEN 'INDICACAO_CLIENTE' THEN 'Indicação de clientes' WHEN 'CANAL_PROPRIO' THEN 'Canais próprios'
                    ELSE 'Outros' END AS grupo_nome,
               (grupo IN ('ARQUITETOS', 'CONSTRUTORAS')) AS fl_parceria,
               CASE grupo WHEN 'ARQUITETOS' THEN 1 WHEN 'CONSTRUTORAS' THEN 2 WHEN 'INDICACAO_CLIENTE' THEN 3
                    WHEN 'CANAL_PROPRIO' THEN 4 ELSE 5 END AS ordem_grupo
        FROM s_origem_contato
        UNION ALL SELECT -1, 'N/D', 'Não informado', 'N/D', 'Não informado', false, 9
    """,
    "dim_parceiro": """
        SELECT p.id AS sk_parceiro,
               CASE p.tipo WHEN 'ESCRITORIO' THEN 'Escritório de arquitetura' ELSE 'Construtora' END AS tipo,
               p.nome_fantasia AS nome, p.razao_social, p.bairro, p.p_comissao_padrao,
               p.dt_inicio_parceria, year(p.dt_inicio_parceria) AS ano_inicio_parceria, p.ativo,
               u.nome AS vendedor_relacionamento
        FROM s_parceiro p LEFT JOIN s_usuario u ON u.id = p.vendedor_relacionamento_id
        UNION ALL SELECT -1, 'Sem parceiro', 'Sem parceiro', 'Sem parceiro', NULL, NULL, NULL, -1, false, NULL
        UNION ALL SELECT -2, 'Outros / não cadastrado', 'Outros / não cadastrado', 'Parceiro informado em texto livre',
                         NULL, NULL, NULL, -1, false, NULL
    """,
    "dim_fase": """
        SELECT id AS sk_fase, nome, grupo,
               CASE grupo WHEN 'ABERTO' THEN 'Em aberto' WHEN 'GANHO' THEN 'Ganho' ELSE 'Perdido' END AS grupo_nome,
               ordem FROM s_fase
    """,
    "dim_motivo_perda": """
        SELECT id AS sk_motivo_perda, nome FROM s_motivo_perda
        UNION ALL SELECT -1, 'Não se aplica'
    """,
    "dim_status_etapa": """
        SELECT id AS sk_status_etapa, nome, ordem, qtd_dias_limite, fl_pos_venda FROM s_status_etapa
        UNION ALL SELECT -1, 'NÃO DEFINIDO', 0, 0, false
    """,
    "dim_item": """
        SELECT i.id AS sk_item, i.codigo, i.descricao, i.categoria_item_id AS sk_categoria_item,
               c.nome AS categoria, c.fl_servico, i.unidade_medida, i.vl_referencia, i.vl_custo_referencia,
               f.nome_fantasia AS fornecedor
        FROM s_item_catalogo i JOIN s_categoria_item c ON c.id = i.categoria_item_id
        LEFT JOIN s_fornecedor f ON f.id = i.fornecedor_id
    """,
    "dim_categoria_item": "SELECT id AS sk_categoria_item, nome, fl_servico FROM s_categoria_item",
    "dim_ambiente": """
        SELECT id AS sk_ambiente, nome FROM s_ambiente UNION ALL SELECT -1, 'Não informado'
    """,
    "dim_forma_pagamento": """
        SELECT id AS sk_forma_pagamento, nome FROM s_forma_pagamento UNION ALL SELECT -1, 'Não informada'
    """,
    "dim_faixa_valor": """
        SELECT * FROM (VALUES
            (1, 'Até R$ 20 mil', 0.0, 20000.0, 1), (2, 'R$ 20 a 70 mil', 20000.0, 70000.0, 2),
            (3, 'R$ 70 a 200 mil', 70000.0, 200000.0, 3), (4, 'R$ 200 a 400 mil', 200000.0, 400000.0, 4),
            (5, 'Acima de R$ 400 mil', 400000.0, 1e12, 5), (-1, 'Sem valor', NULL, NULL, 9))
            AS t(sk_faixa_valor, faixa, limite_inferior, limite_superior, ordem)
    """,
    # Régua de SLA da diretoria: conversão (quanto maior, melhor) e perda (leitura invertida).
    "dim_faixa_sla": """
        SELECT * FROM (VALUES
            ('CONVERSAO', 1, 'Crítico',   0.0,  10.0, 1), ('CONVERSAO', 2, 'Ruim',     10.0, 15.0, 2),
            ('CONVERSAO', 3, 'Regular',  15.0,  25.0, 3), ('CONVERSAO', 4, 'Boa',      25.0, 40.0, 4),
            ('CONVERSAO', 5, 'Excelente', 40.0, 100.0, 5),
            ('PERDA', 1, 'Excelente',  0.0,  10.0, 1), ('PERDA', 2, 'Boa',      10.0, 15.0, 2),
            ('PERDA', 3, 'Regular',   15.0,  25.0, 3), ('PERDA', 4, 'Ruim',     25.0, 40.0, 4),
            ('PERDA', 5, 'Crítico',   40.0, 100.0, 5))
            AS t(tipo, sk_faixa_sla, faixa, limite_inferior_exclusivo, limite_superior_inclusivo, ordem)
    """,
}

# Fatos: (nome, coluna de partição já chamada `ano` no SELECT)
FATOS: dict[str, str] = {
    "ft_orcamento": """
        WITH base AS (
          SELECT o.*, c.cliente_canonico_id,
                 row_number() OVER (PARTITION BY c.cliente_canonico_id ORDER BY o.dt_cadastro, o.id) AS ordem_cliente
          FROM s_orcamento o JOIN s_cliente c ON c.id = o.cliente_id WHERE o.fl_conta_bi)
        SELECT year(b.dt_cadastro) AS ano, b.id AS sk_orcamento, b.nr_orcamento,
               sk_data(b.dt_cadastro) AS sk_data_cadastro, sk_data(b.dt_fechamento) AS sk_data_fechamento,
               b.unidade_id AS sk_unidade, b.vendedor_id AS sk_vendedor, b.cliente_canonico_id AS sk_cliente,
               COALESCE(b.origem_contato_id, -1) AS sk_canal,
               sk_parceiro_de(b.parceiro_id, b.parceiro_texto_livre) AS sk_parceiro,
               b.fase_id AS sk_fase, COALESCE(b.motivo_perda_id, -1) AS sk_motivo_perda,
               faixa_valor(b.vl_total_bruto) AS sk_faixa_valor, COALESCE(b.projetista_3d_id, -1) AS sk_projetista,
               b.grupo_fase, b.status_operacional,
               b.qtd_itens, b.vl_total_bruto AS vl_bruto, b.vl_desconto, b.porc_desconto,
               b.vl_total_liquido AS vl_liquido, b.vl_custo_itens AS vl_custo, b.vl_margem_custo,
               COALESCE(b.vl_comissao_vendedor, 0) AS vl_comissao_vendedor,
               COALESCE(b.vl_comissao_parceiro, 0) AS vl_comissao_parceiro,
               COALESCE(b.vl_comissao_3d, 0) AS vl_comissao_3d,
               b.dias_ate_fechar, b.qtd_follow_ups, b.qtd_revisoes,
               CASE WHEN b.grupo_fase = 'GANHO' THEN 1 ELSE 0 END AS fl_ganho,
               CASE WHEN b.grupo_fase = 'PERDIDO' THEN 1 ELSE 0 END AS fl_perdido,
               CASE WHEN b.grupo_fase = 'ABERTO' THEN 1 ELSE 0 END AS fl_aberto,
               CASE WHEN b.grupo_fase IN ('GANHO', 'PERDIDO') THEN 1 ELSE 0 END AS fl_fechado,
               CASE WHEN b.fl_valor_zero THEN 1 ELSE 0 END AS fl_valor_zero,
               CASE WHEN b.fl_divergencia_itens THEN 1 ELSE 0 END AS fl_divergencia_itens,
               CASE WHEN b.fl_dt_finalizou_sentinela OR b.fl_fechou_antes_cadastro THEN 1 ELSE 0 END AS fl_data_corrigida,
               CASE WHEN b.ordem_cliente > 1 THEN 1 ELSE 0 END AS fl_cliente_recorrente,
               CASE WHEN b.parceiro_id IS NOT NULL THEN 1 ELSE 0 END AS fl_com_parceiro,
               b.dt_cadastro, b.dt_fechamento
        FROM base b
    """,
    "ft_venda": """
        WITH pag AS (
          SELECT r.orcamento_id, MIN(pg.dt_pagamento) AS dt_primeiro_pagamento, SUM(pg.vl_pago) AS vl_recebido,
                 COUNT(DISTINCT p.id) AS qtd_parcelas,
                 SUM(CASE WHEN p.fl_vencida_sem_pagamento THEN 1 ELSE 0 END) AS qtd_parcelas_vencidas
          FROM s_recebimento r JOIN s_parcela p ON p.recebimento_id = r.id
          LEFT JOIN s_pagamento pg ON pg.parcela_id = p.id
          WHERE r.dt_cancelamento IS NULL GROUP BY 1)
        SELECT year(o.dt_fechamento) AS ano, o.id AS sk_orcamento, o.nr_orcamento,
               sk_data(o.dt_fechamento) AS sk_data_ganho, sk_data(o.dt_cadastro) AS sk_data_cadastro,
               sk_data(pag.dt_primeiro_pagamento) AS sk_data_primeiro_pagamento,
               o.unidade_id AS sk_unidade, o.vendedor_id AS sk_vendedor, c.cliente_canonico_id AS sk_cliente,
               COALESCE(o.origem_contato_id, -1) AS sk_canal,
               sk_parceiro_de(o.parceiro_id, o.parceiro_texto_livre) AS sk_parceiro,
               faixa_valor(o.vl_total_bruto) AS sk_faixa_valor, COALESCE(o.forma_pagamento_id, -1) AS sk_forma_pagamento,
               COALESCE(o.projetista_3d_id, -1) AS sk_projetista,
               o.qtd_itens, o.vl_total_bruto AS vl_bruto, o.vl_desconto, o.porc_desconto, o.vl_total_liquido AS vl_liquido,
               o.vl_custo_itens AS vl_custo, o.vl_margem_custo,
               CASE WHEN o.vl_total_bruto > 0 THEN o.vl_total_liquido / o.vl_total_bruto END AS margem_liquida,
               CASE WHEN o.vl_total_liquido > 0 THEN o.vl_margem_custo / o.vl_total_liquido END AS margem_sobre_custo,
               COALESCE(o.vl_comissao_vendedor, 0) AS vl_comissao_vendedor,
               COALESCE(o.vl_comissao_parceiro, 0) AS vl_comissao_parceiro,
               COALESCE(o.vl_comissao_3d, 0) AS vl_comissao_3d,
               COALESCE(o.vl_comissao_vendedor, 0) + COALESCE(o.vl_comissao_parceiro, 0) + COALESCE(o.vl_comissao_3d, 0)
                   AS vl_comissao_total,
               o.dias_ate_fechar, COALESCE(pag.qtd_parcelas, 0) AS qtd_parcelas,
               COALESCE(pag.vl_recebido, 0) AS vl_recebido, COALESCE(pag.qtd_parcelas_vencidas, 0) AS qtd_parcelas_vencidas,
               CASE WHEN o.fl_ganho_sem_recebimento THEN 1 ELSE 0 END AS fl_sem_recebimento,
               CASE WHEN o.fl_valor_zero THEN 1 ELSE 0 END AS fl_valor_zero,
               CASE WHEN o.parceiro_id IS NOT NULL THEN 1 ELSE 0 END AS fl_com_parceiro,
               1 AS qtd_vendas, o.dt_fechamento AS dt_ganho
        FROM s_orcamento o JOIN s_cliente c ON c.id = o.cliente_id
        LEFT JOIN pag ON pag.orcamento_id = o.id
        WHERE o.fl_conta_bi AND o.grupo_fase = 'GANHO'
    """,
    "ft_comissao": """
        SELECT CAST(left(c.competencia, 4) AS INTEGER) AS ano, c.id AS sk_comissao, c.orcamento_id AS sk_orcamento,
               c.competencia, sk_data(CAST(c.competencia || '-01' AS DATE)) AS sk_data_competencia,
               sk_data(c.dt_apuracao) AS sk_data_apuracao, sk_data(c.dt_pagamento) AS sk_data_pagamento,
               c.tipo, COALESCE(c.usuario_id, -1) AS sk_vendedor, COALESCE(c.parceiro_id, -1) AS sk_parceiro,
               o.unidade_id AS sk_unidade, COALESCE(o.origem_contato_id, -1) AS sk_canal,
               c.p_comissao, c.p_comissao_esperado, c.vl_base, c.vl_comissao, c.vl_diferenca_esperado,
               CASE WHEN c.fl_pago THEN 1 ELSE 0 END AS fl_pago,
               CASE WHEN c.fl_comissao_divergente THEN 1 ELSE 0 END AS fl_divergente
        FROM s_comissao c JOIN s_orcamento o ON o.id = c.orcamento_id WHERE o.fl_conta_bi
    """,
    "ft_funil_posicao": f"""
        WITH meses AS (
          SELECT LEAST(last_day(CAST(m AS DATE)), CAST({T} AS DATE)) AS fim_mes
          FROM (SELECT unnest(generate_series(DATE '2021-01-01', CAST({T} AS DATE), INTERVAL 1 MONTH)) AS m)),
        pos AS (
          SELECT m.fim_mes, o.id, o.unidade_id, o.vendedor_id, o.origem_contato_id, o.parceiro_id,
                 o.parceiro_texto_livre, o.vl_total_bruto, o.vl_total_liquido, h.fase_id
          FROM meses m
          JOIN s_orcamento o ON o.fl_conta_bi AND CAST(o.dt_cadastro AS DATE) <= m.fim_mes
          JOIN s_orcamento_fase_hist h ON h.orcamento_id = o.id AND CAST(h.dt_entrada AS DATE) <= m.fim_mes
          QUALIFY row_number() OVER (PARTITION BY m.fim_mes, o.id ORDER BY h.dt_entrada DESC, h.id DESC) = 1)
        SELECT year(p.fim_mes) AS ano, sk_data(p.fim_mes) AS sk_data_posicao, p.fim_mes AS dt_posicao,
               p.unidade_id AS sk_unidade, p.vendedor_id AS sk_vendedor, COALESCE(p.origem_contato_id, -1) AS sk_canal,
               sk_parceiro_de(p.parceiro_id, p.parceiro_texto_livre) AS sk_parceiro, p.fase_id AS sk_fase,
               f.grupo AS grupo_fase, COUNT(*) AS qtd_orcamentos,
               SUM(p.vl_total_bruto) AS vl_bruto, SUM(p.vl_total_liquido) AS vl_liquido
        FROM pos p JOIN s_fase f ON f.id = p.fase_id
        GROUP BY ALL
    """,
    "ft_orcamento_item": """
        SELECT year(o.dt_cadastro) AS ano, i.id AS sk_orcamento_item, o.id AS sk_orcamento,
               sk_data(o.dt_cadastro) AS sk_data_cadastro, i.item_catalogo_id AS sk_item,
               i.categoria_item_id AS sk_categoria_item, COALESCE(i.ambiente_id, -1) AS sk_ambiente,
               o.unidade_id AS sk_unidade, o.vendedor_id AS sk_vendedor, COALESCE(o.origem_contato_id, -1) AS sk_canal,
               o.fase_id AS sk_fase, i.qtd, i.vl_unitario, i.vl_total, COALESCE(i.vl_custo, 0) AS vl_custo,
               i.vl_margem_custo, CASE WHEN i.fl_cancelado THEN 1 ELSE 0 END AS fl_cancelado,
               CASE WHEN o.grupo_fase = 'GANHO' THEN 1 ELSE 0 END AS fl_ganho
        FROM s_orcamento_item i JOIN s_orcamento o ON o.id = i.orcamento_id WHERE o.fl_conta_bi
    """,
    "ft_parcela": """
        SELECT year(p.dt_vencimento) AS ano, p.id AS sk_parcela, r.orcamento_id AS sk_orcamento,
               sk_data(p.dt_vencimento) AS sk_data_vencimento, sk_data(p.dt_primeiro_pagamento) AS sk_data_pagamento,
               r.forma_pagamento_id AS sk_forma_pagamento, c.cliente_canonico_id AS sk_cliente,
               o.vendedor_id AS sk_vendedor, o.unidade_id AS sk_unidade,
               p.nr_parcela, r.nr_parcelas, p.vl_parcela, COALESCE(p.vl_pago_total, 0) AS vl_pago,
               CASE WHEN p.fl_pago THEN 1 ELSE 0 END AS fl_pago,
               CASE WHEN p.fl_vencida_sem_pagamento THEN 1 ELSE 0 END AS fl_vencida_sem_pagamento,
               COALESCE(p.dias_atraso_pagamento, 0) AS dias_atraso_pagamento
        FROM s_parcela p JOIN s_recebimento r ON r.id = p.recebimento_id
        JOIN s_orcamento o ON o.id = r.orcamento_id JOIN s_cliente c ON c.id = o.cliente_id
        WHERE o.fl_conta_bi AND p.dt_cancelamento IS NULL
    """,
    "ft_follow_up": """
        SELECT year(f.dt_lanc) AS ano, f.id AS sk_follow_up, f.orcamento_id AS sk_orcamento,
               sk_data(f.dt_lanc) AS sk_data, f.usuario_id AS sk_vendedor, o.unidade_id AS sk_unidade,
               COALESCE(o.origem_contato_id, -1) AS sk_canal, f.tipo_contato,
               CASE WHEN f.dt_proximo_contato IS NOT NULL THEN 1 ELSE 0 END AS fl_com_proximo_contato,
               1 AS qtd_contatos
        FROM s_follow_up f JOIN s_orcamento o ON o.id = f.orcamento_id WHERE o.fl_conta_bi
    """,
}
