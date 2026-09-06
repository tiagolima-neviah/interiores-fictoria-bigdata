"""Catálogo de achados de qualidade sobre o bronze (estado corrente).

Cada achado tem um id estável, a consulta que o evidencia (DuckDB), a métrica-resumo que
a Nota Técnica cita e a regra que a silver aplica. Os notebooks de auditoria são gerados
a partir desta lista e executados de verdade: a nota é escrita com o observado, nunca antes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

VENDA = "tipo_orcamento_id = 1 AND dt_cancelou IS NULL"
FECHADOS = f"{VENDA} AND fase_id IN (6, 7)"


@dataclass(frozen=True)
class Achado:
    id: str
    titulo: str
    caderno: int  # 1 = cadastro e funil · 2 = financeiro e obra
    sql: str  # consulta de evidência (tabela mostrada no notebook)
    metrica_sql: str  # escalar-resumo (taxa ou contagem) para a Nota Técnica
    formato: str  # como exibir a métrica: 'pct' | 'int'
    por_que_importa: str
    regra_silver: str
    grafico: str | None = (
        None  # consulta opcional (2 colunas: rótulo, valor) para um gráfico de barras
    )
    tags: tuple[str, ...] = field(default_factory=tuple)


ACHADOS: list[Achado] = [
    Achado(
        "ACH-01",
        "Data-sentinela 1900-01-01 no fechamento",
        1,
        f"""SELECT fase_id, COUNT(*) AS orcamentos,
                   SUM(CASE WHEN dt_finalizou = TIMESTAMP '1900-01-01' THEN 1 ELSE 0 END) AS sentinela
            FROM b_orcamento WHERE {FECHADOS} GROUP BY fase_id ORDER BY fase_id""",
        f"""SELECT AVG(CASE WHEN dt_finalizou = TIMESTAMP '1900-01-01' THEN 1.0 ELSE 0.0 END)
            FROM b_orcamento WHERE {FECHADOS}""",
        "pct",
        "Um orçamento fechado com data 1900 entra em qualquer filtro de período como se fosse do "
        "século passado e some dos relatórios do ano; somado a datas nulas, distorce prazos médios.",
        "`dt_finalizou` sentinela vira NULL e a data de fechamento passa a ser a entrada na fase "
        "final registrada na trilha (`orcamento_fase_hist`), que não tem sentinela; flag "
        "`fl_dt_finalizou_sentinela`.",
    ),
    Achado(
        "ACH-02",
        "Fechamento anterior ao cadastro",
        1,
        f"""SELECT id, nr_orcamento, dt_cadastro, dt_finalizou,
                   date_diff('day', dt_cadastro, dt_finalizou) AS dias
            FROM b_orcamento WHERE {FECHADOS} AND dt_finalizou > TIMESTAMP '1900-01-01'
              AND dt_finalizou < dt_cadastro ORDER BY dias LIMIT 15""",
        f"""SELECT AVG(CASE WHEN dt_finalizou > TIMESTAMP '1900-01-01' AND dt_finalizou < dt_cadastro
                            THEN 1.0 ELSE 0.0 END) FROM b_orcamento WHERE {FECHADOS}""",
        "pct",
        "Dias até fechar negativos derrubam a média e a mediana de prazo; a causa típica é relógio "
        "de estação errado ou digitação manual da data de fechamento.",
        "A data de fechamento confiável vem da trilha de fases; o valor registrado fica preservado "
        "em `dt_finalizou_registrado` com a flag `fl_fechou_antes_cadastro`.",
    ),
    Achado(
        "ACH-03",
        "Orçamentos de valor zero",
        1,
        f"""SELECT YEAR(dt_cadastro) AS ano, COUNT(*) AS orcamentos,
                   SUM(CASE WHEN vl_total_bruto = 0 THEN 1 ELSE 0 END) AS valor_zero
            FROM b_orcamento WHERE {VENDA} GROUP BY 1 ORDER BY 1""",
        f"SELECT AVG(CASE WHEN vl_total_bruto = 0 THEN 1.0 ELSE 0.0 END) FROM b_orcamento WHERE {VENDA}",
        "pct",
        "Valor zero conta como orçamento no volume e não conta em dinheiro: ticket médio e "
        "conversão em valor ficam subestimados sem que ninguém perceba.",
        "Mantido no funil (é um orçamento real) com `fl_valor_zero`; a gold exclui esses "
        "orçamentos das médias de ticket e os mostra como indicador próprio.",
    ),
    Achado(
        "ACH-04",
        "Total bruto diferente da soma dos itens",
        1,
        """SELECT YEAR(o.dt_cadastro) AS ano, COUNT(*) AS orcamentos,
                  SUM(CASE WHEN ABS(o.vl_total_bruto - COALESCE(i.soma, 0)) > 0.05 THEN 1 ELSE 0 END)
                      AS divergentes,
                  SUM(CASE WHEN ABS(o.vl_total_bruto - COALESCE(i.soma_com_cancelados, 0)) <= 0.05
                            AND ABS(o.vl_total_bruto - COALESCE(i.soma, 0)) > 0.05 THEN 1 ELSE 0 END)
                      AS cancelado_somado
           FROM b_orcamento o
           LEFT JOIN (SELECT orcamento_id,
                             SUM(CASE WHEN dt_cancelou IS NULL THEN vl_total ELSE 0 END) AS soma,
                             SUM(vl_total) AS soma_com_cancelados
                      FROM b_orcamento_item GROUP BY 1) i ON i.orcamento_id = o.id
           WHERE o.dt_cancelou IS NULL GROUP BY 1 ORDER BY 1""",
        """SELECT AVG(CASE WHEN ABS(o.vl_total_bruto - COALESCE(i.soma, 0)) > 0.05 THEN 1.0 ELSE 0.0 END)
           FROM b_orcamento o
           LEFT JOIN (SELECT orcamento_id, SUM(vl_total) AS soma FROM b_orcamento_item
                      WHERE dt_cancelou IS NULL GROUP BY 1) i ON i.orcamento_id = o.id
           WHERE o.dt_cancelou IS NULL""",
        "pct",
        "O cabeçalho é o que a empresa vê; os itens são o que ela vendeu. Quando divergem, o "
        "relatório por categoria de item não fecha com o total do orçamento. Aqui a divergência é "
        "um bug antigo do sistema (2021-2022): item cancelado continuou somado.",
        "A silver recalcula `vl_bruto_itens` a partir dos itens não cancelados e marca "
        "`fl_divergencia_itens`; a gold usa o cabeçalho (o que foi negociado) e expõe a divergência.",
    ),
    Achado(
        "ACH-05",
        "Clientes duplicados por grafia",
        1,
        """WITH n AS (
             SELECT id, nome,
                    regexp_replace(strip_accents(lower(trim(nome))), '\\s+', ' ', 'g') AS nome_norm
             FROM b_cliente)
           SELECT nome_norm, COUNT(*) AS cadastros, string_agg(nome, ' | ' ORDER BY id) AS grafias
           FROM n GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY 2 DESC, 1 LIMIT 15""",
        """WITH n AS (
             SELECT regexp_replace(strip_accents(lower(trim(nome))), '\\s+', ' ', 'g') AS nome_norm
             FROM b_cliente)
           SELECT 1.0 - COUNT(DISTINCT nome_norm) * 1.0 / COUNT(*) FROM n""",
        "pct",
        "O mesmo cliente com três grafias vira três clientes: recorrência subestimada, ranking de "
        "clientes fiéis errado e premiação indo para a pessoa errada.",
        "`nome_normalizado` (minúsculas, sem acento, espaços colapsados) e `cliente_canonico_id` "
        "(o menor id do grupo); a dimensão de cliente da gold usa o canônico.",
    ),
    Achado(
        "ACH-06",
        "Endereços sem CEP ou sem bairro",
        1,
        """SELECT tipo, COUNT(*) AS enderecos,
                  SUM(CASE WHEN cep IS NULL THEN 1 ELSE 0 END) AS sem_cep,
                  SUM(CASE WHEN bairro IS NULL THEN 1 ELSE 0 END) AS sem_bairro
           FROM b_endereco GROUP BY 1 ORDER BY 2 DESC""",
        "SELECT AVG(CASE WHEN cep IS NULL OR bairro IS NULL THEN 1.0 ELSE 0.0 END) FROM b_endereco",
        "pct",
        "Bairro é a geografia do público-alvo (Jardim Europa para cima); sem ele, a leitura por "
        "região perde parte da base, e ausência não se preenche com chute.",
        "Ausência preservada como NULL; a dimensão de cliente usa o bairro do endereço principal e "
        "o membro 'Não informado' quando faltar.",
    ),
    Achado(
        "ACH-07",
        "Parceiro informado em texto livre, sem cadastro",
        1,
        """SELECT oc.codigo AS canal, COUNT(*) AS orcamentos,
                  SUM(CASE WHEN o.ds_objetivo LIKE 'Indicação:%' THEN 1 ELSE 0 END) AS com_texto_livre
           FROM b_orcamento o JOIN b_origem_contato oc ON oc.id = o.origem_contato_id
           WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL GROUP BY 1 ORDER BY 2 DESC""",
        f"""SELECT AVG(CASE WHEN ds_objetivo LIKE 'Indicação:%' THEN 1.0 ELSE 0.0 END)
            FROM b_orcamento WHERE {VENDA} AND parceiro_id IS NULL AND origem_contato_id = 9""",
        "pct",
        "Indicações de arquiteto que não viraram cadastro caem em 'Outros' e o parceiro não recebe "
        "o crédito; é volume de parceria invisível para a premiação.",
        "A silver extrai `parceiro_texto_livre` do objetivo e mantém o canal OUTROS (regra do "
        "negócio: parceiro é PJ cadastrada); a gold mostra 'Outros / não cadastrado' como membro.",
    ),
    Achado(
        "ACH-08",
        "Ganhos sem trilha de etapas de execução",
        1,
        """SELECT YEAR(o.dt_cadastro) AS ano, COUNT(*) AS ganhos,
                  SUM(CASE WHEN e.orcamento_id IS NULL THEN 1 ELSE 0 END) AS sem_etapas
           FROM b_orcamento o
           LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_orcamento_etapa) e ON e.orcamento_id = o.id
           WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL AND o.fase_id = 6
           GROUP BY 1 ORDER BY 1""",
        f"""SELECT AVG(CASE WHEN e.orcamento_id IS NULL THEN 1.0 ELSE 0.0 END)
            FROM b_orcamento o
            LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_orcamento_etapa) e ON e.orcamento_id = o.id
            WHERE {VENDA} AND o.fase_id = 6""",
        "pct",
        "Sem trilha, o status operacional é 'não definido' e a obra não aparece no acompanhamento; "
        "concentra-se nos ganhos antigos, antes do processo existir.",
        "Status operacional derivado: 'NÃO DEFINIDO' quando não há etapa; `fl_sem_trilha_execucao`.",
    ),
    Achado(
        "ACH-09",
        "Follow-up ausente depende do vendedor",
        1,
        """SELECT u.nome AS vendedor, COUNT(*) AS orcamentos,
                  ROUND(AVG(CASE WHEN f.orcamento_id IS NULL THEN 1.0 ELSE 0.0 END), 3) AS sem_follow_up
           FROM b_orcamento o JOIN b_usuario u ON u.id = o.vendedor_id
           LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_follow_up) f ON f.orcamento_id = o.id
           WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL
           GROUP BY 1 HAVING COUNT(*) >= 100 ORDER BY 3 DESC""",
        f"""SELECT AVG(CASE WHEN f.orcamento_id IS NULL THEN 1.0 ELSE 0.0 END)
            FROM b_orcamento o
            LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_follow_up) f ON f.orcamento_id = o.id
            WHERE {VENDA}""",
        "pct",
        "O follow-up é a trilha de interação; se metade dos vendedores não registra, qualquer "
        "análise de esforço comercial compara disciplina de registro, não trabalho.",
        "`qtd_follow_ups` por orçamento (zero quando não há); a gold expõe a métrica por vendedor "
        "como indicador de aderência ao processo, não de esforço.",
        grafico="""SELECT u.nome, ROUND(AVG(CASE WHEN f.orcamento_id IS NULL THEN 1.0 ELSE 0.0 END), 3)
                   FROM b_orcamento o JOIN b_usuario u ON u.id = o.vendedor_id
                   LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_follow_up) f ON f.orcamento_id = o.id
                   WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL
                   GROUP BY 1 HAVING COUNT(*) >= 100 ORDER BY 2 DESC""",
    ),
    Achado(
        "ACH-10",
        "Fora do escopo do BI: tipos não-venda e cancelados",
        1,
        """SELECT t.nome AS tipo,
                  SUM(CASE WHEN o.dt_cancelou IS NULL THEN 1 ELSE 0 END) AS ativos,
                  SUM(CASE WHEN o.dt_cancelou IS NOT NULL THEN 1 ELSE 0 END) AS cancelados
           FROM b_orcamento o JOIN b_tipo_orcamento t ON t.id = o.tipo_orcamento_id
           GROUP BY 1 ORDER BY 2 DESC""",
        "SELECT AVG(CASE WHEN tipo_orcamento_id <> 1 OR dt_cancelou IS NOT NULL THEN 1.0 ELSE 0.0 END) "
        "FROM b_orcamento",
        "pct",
        "Assistência, garantia e cortesia são orçamentos no sistema e não são vendas; cancelados "
        "saem de todas as contas. Sem o filtro, volume e conversão vêm errados desde a primeira tela.",
        "Flag `fl_conta_bi` na silver (Venda e não cancelado); a gold só carrega linhas com a flag.",
    ),
    Achado(
        "ACH-11",
        "Fase atual × trilha e data registrada × trilha",
        1,
        """WITH ult AS (
             SELECT orcamento_id, fase_id, dt_entrada,
                    row_number() OVER (PARTITION BY orcamento_id ORDER BY dt_entrada DESC, id DESC) AS rn
             FROM b_orcamento_fase_hist)
           SELECT
             SUM(CASE WHEN o.fase_id = u.fase_id THEN 1 ELSE 0 END) AS fase_coerente,
             SUM(CASE WHEN o.fase_id <> u.fase_id THEN 1 ELSE 0 END) AS fase_divergente,
             SUM(CASE WHEN o.fase_id IN (6, 7) AND o.dt_finalizou = u.dt_entrada THEN 1 ELSE 0 END)
                 AS data_igual_trilha,
             SUM(CASE WHEN o.fase_id IN (6, 7) AND o.dt_finalizou <> u.dt_entrada THEN 1 ELSE 0 END)
                 AS data_diverge_trilha
           FROM b_orcamento o JOIN ult u ON u.orcamento_id = o.id AND u.rn = 1
           WHERE o.dt_cancelou IS NULL""",
        """WITH ult AS (
             SELECT orcamento_id, fase_id,
                    row_number() OVER (PARTITION BY orcamento_id ORDER BY dt_entrada DESC, id DESC) AS rn
             FROM b_orcamento_fase_hist)
           SELECT AVG(CASE WHEN o.fase_id = u.fase_id THEN 1.0 ELSE 0.0 END)
           FROM b_orcamento o JOIN ult u ON u.orcamento_id = o.id AND u.rn = 1""",
        "pct",
        "A trilha de fases é a fonte da posição histórica do funil; se ela não bater com a fase "
        "atual do cabeçalho, nenhum 'quantos estavam abertos em agosto' é confiável.",
        "A trilha é a verdade para datas de fase e fechamento; o cabeçalho é a verdade para "
        "valores e vínculos. Divergências de data são as dos achados 01 e 02.",
    ),
    # --- caderno 2: financeiro e obra ---
    Achado(
        "ACH-12",
        "Comissão apurada com percentual diferente do orçamento",
        2,
        """SELECT c.tipo, COUNT(*) AS comissoes,
                  SUM(CASE WHEN c.tipo = 'VENDEDOR' AND c.p_comissao <> o.p_comissao_vendedor THEN 1
                           WHEN c.tipo = 'PARCEIRO' AND c.p_comissao <> o.p_comissao_parceiro THEN 1
                           WHEN c.tipo = '3D' AND c.p_comissao <> o.p_comissao_3d THEN 1 ELSE 0 END)
                      AS divergentes
           FROM b_comissao c JOIN b_orcamento o ON o.id = c.orcamento_id GROUP BY 1 ORDER BY 2 DESC""",
        """SELECT AVG(CASE WHEN c.tipo = 'VENDEDOR' AND c.p_comissao <> o.p_comissao_vendedor THEN 1.0
                           WHEN c.tipo = 'PARCEIRO' AND c.p_comissao <> o.p_comissao_parceiro THEN 1.0
                           WHEN c.tipo = '3D' AND c.p_comissao <> o.p_comissao_3d THEN 1.0 ELSE 0.0 END)
           FROM b_comissao c JOIN b_orcamento o ON o.id = c.orcamento_id WHERE c.tipo <> 'SUPERVISOR'""",
        "pct",
        "Comissão paga com percentual diferente do negociado é dinheiro saindo errado; a régua da "
        "diretoria ('quanto pagamos de comissão') precisa do apurado E do esperado.",
        "`p_comissao_esperado` e `fl_comissao_divergente` na silver; a gold carrega o valor apurado "
        "(o que foi pago) e a diferença contra o esperado como medida.",
    ),
    Achado(
        "ACH-13",
        "Parcelas vencidas sem pagamento e pagamentos em atraso",
        2,
        """SELECT YEAR(p.dt_vencimento) AS ano, COUNT(*) AS parcelas,
                  SUM(CASE WHEN NOT p.fl_pago AND p.dt_vencimento < DATE '2026-09-04' THEN 1 ELSE 0 END)
                      AS vencidas_sem_pagamento,
                  SUM(CASE WHEN pg.dt_pagamento > p.dt_vencimento + INTERVAL 5 DAY THEN 1 ELSE 0 END)
                      AS pagas_com_atraso
           FROM b_parcela p LEFT JOIN b_pagamento pg ON pg.parcela_id = p.id
           GROUP BY 1 ORDER BY 1""",
        """SELECT AVG(CASE WHEN NOT fl_pago AND dt_vencimento < DATE '2026-09-04' THEN 1.0 ELSE 0.0 END)
           FROM b_parcela""",
        "pct",
        "Inadimplência e atraso são a diferença entre venda e caixa; a comissão do vendedor só é "
        "liberada depois do primeiro pagamento, então atraso no cliente vira atraso na equipe.",
        "`fl_vencida_sem_pagamento` e `dias_atraso_pagamento` na silver; fato de parcelas na gold com "
        "as datas de vencimento e pagamento no calendário.",
    ),
    Achado(
        "ACH-14",
        "Auditoria guarda valores como texto com vírgula",
        2,
        """SELECT ds_campo, COUNT(*) AS alteracoes,
                  MIN(vl_novo) AS exemplo_menor, MAX(vl_novo) AS exemplo_maior
           FROM b_auditoria_orcamento WHERE ds_campo IN ('vl_total_liquido', 'vl_desconto')
           GROUP BY 1 ORDER BY 2 DESC""",
        """SELECT COUNT(*) FROM b_auditoria_orcamento
           WHERE ds_campo IN ('vl_total_liquido', 'vl_desconto') AND vl_novo <> '(criação)'""",
        "int",
        "A auditoria é a única trilha de renegociação (quantas vezes o valor mudou até fechar), mas "
        "os valores estão em texto pt-BR: '1.234,56'. Sem conversão, nenhuma média sai.",
        "`vl_antigo_num`/`vl_novo_num` convertidos (remove pontos, troca vírgula por ponto) só para "
        "campos monetários; `qtd_revisoes` por orçamento = alterações de `vl_total_liquido`.",
    ),
    Achado(
        "ACH-15",
        "Ganhos sem recebimento e comissão ainda não apurada",
        2,
        """SELECT YEAR(o.dt_cadastro) AS ano, COUNT(*) AS ganhos,
                  SUM(CASE WHEN r.orcamento_id IS NULL THEN 1 ELSE 0 END) AS sem_recebimento,
                  SUM(CASE WHEN c.orcamento_id IS NULL THEN 1 ELSE 0 END) AS sem_comissao
           FROM b_orcamento o
           LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_recebimento) r ON r.orcamento_id = o.id
           LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_comissao) c ON c.orcamento_id = o.id
           WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL AND o.fase_id = 6
           GROUP BY 1 ORDER BY 1""",
        f"""SELECT AVG(CASE WHEN r.orcamento_id IS NULL THEN 1.0 ELSE 0.0 END)
            FROM b_orcamento o
            LEFT JOIN (SELECT DISTINCT orcamento_id FROM b_recebimento) r ON r.orcamento_id = o.id
            WHERE {VENDA} AND o.fase_id = 6""",
        "pct",
        "Ganho sem recebimento é venda de valor zero (achado 03) ou contrato ainda não emitido; "
        "comissão sem apuração no mês corrente é normal (apura no mês seguinte). Distinguir os dois "
        "evita alarme falso.",
        "Nenhum preenchimento: a gold trata venda sem recebimento como 'sem contrato' e comissão "
        "como 'a apurar' pelo calendário de competência.",
    ),
    Achado(
        "ACH-16",
        "Medições não realizadas e instalações com problema",
        2,
        """SELECT 'medições agendadas' AS item, COUNT(*) AS total,
                  SUM(CASE WHEN dt_realizada IS NULL THEN 1 ELSE 0 END) AS pendentes_ou_nao_realizadas
           FROM b_medicao
           UNION ALL
           SELECT 'instalações', COUNT(*), SUM(CASE WHEN fl_problema THEN 1 ELSE 0 END) FROM b_instalacao""",
        "SELECT AVG(CASE WHEN fl_problema THEN 1.0 ELSE 0.0 END) FROM b_instalacao WHERE dt_fim IS NOT NULL",
        "pct",
        "Problema na instalação é o que gera correção e atraso no pós-venda; medição agendada e não "
        "realizada distorce o prazo até a proposta.",
        "Preservado como está; a gold traz instalação e medição como fatos de obra com as flags.",
    ),
]


def por_caderno(caderno: int) -> list[Achado]:
    return [a for a in ACHADOS if a.caderno == caderno]


def medir(con: duckdb.DuckDBPyConnection, achado: Achado) -> float:
    valor = con.execute(achado.metrica_sql).fetchone()
    return float(valor[0]) if valor and valor[0] is not None else 0.0


def formatar(valor: float, formato: str) -> str:
    if formato == "pct":
        return f"{valor * 100:.2f}%".replace(".", ",")
    return f"{int(round(valor)):,}".replace(",", ".")


def medir_todos(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, str | float]]:
    return {
        a.id: {
            "titulo": a.titulo,
            "valor": medir(con, a),
            "texto": formatar(medir(con, a), a.formato),
        }
        for a in ACHADOS
    }
