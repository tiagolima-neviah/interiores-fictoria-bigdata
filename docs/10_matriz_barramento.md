<a id="topo"></a>

# Matriz de Barramento: dos indicadores da diretoria ao star schema

<!-- nav:start -->
[Home](../README.md) | [← Camada Silver](09_camada_silver.md) | [Camada Gold →](11_camada_gold.md)
<!-- nav:end -->

> O contrato da gold. Parte das perguntas da diretoria ([docs/01, seção 7](01_entendimento_negocio.md)), define o grão de cada fato e as dimensões conformadas que todas compartilham, e mostra como cada indicador é calculado. Quando dois relatórios divergem, é aqui que se descobre qual dos dois saiu do contrato.

## 1. Dimensões conformadas

| dimensão | chave | grão | membros especiais | observações |
|---|---|---|---|---|
| `dim_calendario` | `sk_data` (yyyymmdd) | dia, 2021 a 2027 | -1 "Data inválida" | ano, mês, trimestre, semestre, semana ISO, dia útil, `sk_data_ano_anterior`, `sk_data_dois_anos_antes`, `fl_ate_data_corrente`, `fl_acumulado_ano_comparavel` (jan até o dia corrente, para o rito semestral/anual) |
| `dim_unidade` | `sk_unidade` | showroom | -1 | Jardins, Itaim, Alto de Pinheiros |
| `dim_vendedor` | `sk_vendedor` | pessoa (vendedores, supervisores, projetistas) | -1 | unidade, admissão, desligamento, ativo |
| `dim_cliente` | `sk_cliente` | cliente **canônico** (ACH-05) | -1 | bairro/cidade/UF do endereço principal ("Não informado" quando faltar), grupo do primeiro contato, `fl_recorrente`, `qtd_cadastros_agrupados` |
| `dim_canal` | `sk_canal` | canal de entrada do orçamento | -1 | `grupo_nome` é a leitura "outras origens": Arquitetos, Construtoras, Indicação de clientes, Canais próprios, Outros |
| `dim_parceiro` | `sk_parceiro` | escritório ou construtora | -1 "Sem parceiro", -2 "Outros / não cadastrado" | tipo, comissão padrão, início da parceria, vendedor de relacionamento |
| `dim_fase` | `sk_fase` | fase do funil | | `grupo_nome`: Em aberto, Ganho, Perdido |
| `dim_motivo_perda` | `sk_motivo_perda` | motivo | -1 "Não se aplica" | |
| `dim_status_etapa` | `sk_status_etapa` | etapa de execução | -1 "NÃO DEFINIDO" | |
| `dim_item`, `dim_categoria_item`, `dim_ambiente` | `sk_item`, `sk_categoria_item`, `sk_ambiente` | catálogo | -1 no ambiente | |
| `dim_forma_pagamento` | `sk_forma_pagamento` | forma | -1 | |
| `dim_faixa_valor` | `sk_faixa_valor` | banda de ticket bruto | -1 "Sem valor" | até 20 mil · 20 a 70 · 70 a 200 · 200 a 400 · acima de 400 mil |
| `dim_faixa_sla` | (`tipo`, `sk_faixa_sla`) | banda da régua da diretoria | | CONVERSAO: Crítico 0-10, Ruim 10-15, Regular 15-25, Boa 25-40, Excelente 40+; PERDA: leitura invertida. Tabela de consulta por intervalo, aplicada à taxa agregada |

## 2. Fatos

| fato | grão | partição | medidas principais | dimensões |
|---|---|---|---|---|
| `ft_orcamento` | um orçamento de venda (situação atual) | ano de cadastro | qtd (linhas), `vl_bruto`, `vl_desconto`, `vl_liquido`, `vl_custo`, `vl_margem_custo`, comissões, `dias_ate_fechar`, `qtd_follow_ups`, `qtd_revisoes`, flags 0/1: ganho, perdido, aberto, fechado, valor zero, divergência, data corrigida, cliente recorrente, com parceiro | calendário (cadastro e fechamento), unidade, vendedor, cliente, canal, parceiro, fase, motivo, faixa de valor, projetista |
| `ft_venda` | um orçamento ganho | ano do ganho | `qtd_vendas`, `vl_bruto`, `vl_liquido`, `vl_custo`, `margem_liquida` (líquido/bruto), `margem_sobre_custo`, comissões (vendedor, parceiro, 3D, total), `qtd_parcelas`, `vl_recebido`, parcelas vencidas | calendário (ganho, cadastro, primeiro pagamento), unidade, vendedor, cliente, canal, parceiro, faixa, forma de pagamento |
| `ft_comissao` | uma comissão apurada | ano da competência | `vl_comissao`, `vl_base`, `p_comissao`, `p_comissao_esperado`, `vl_diferenca_esperado`, `fl_pago`, `fl_divergente` | calendário (competência, apuração, pagamento), vendedor ou parceiro, unidade, canal, tipo (degenerada) |
| `ft_funil_posicao` | fim de mês × unidade × vendedor × canal × parceiro × fase | ano da posição | `qtd_orcamentos`, `vl_bruto`, `vl_liquido` | calendário (posição), unidade, vendedor, canal, parceiro, fase |
| `ft_orcamento_item` | um item de orçamento | ano de cadastro | `qtd`, `vl_unitario`, `vl_total`, `vl_custo`, `vl_margem_custo`, `fl_cancelado`, `fl_ganho` | item, categoria, ambiente, unidade, vendedor, canal, fase, calendário |
| `ft_parcela` | uma parcela | ano do vencimento | `vl_parcela`, `vl_pago`, `fl_pago`, `fl_vencida_sem_pagamento`, `dias_atraso_pagamento` | calendário (vencimento, pagamento), forma, cliente, vendedor, unidade |
| `ft_follow_up` | um contato | ano do contato | `qtd_contatos`, `fl_com_proximo_contato` | calendário, vendedor, unidade, canal, tipo (degenerada) |

## 3. Indicadores × fatos

| pergunta da diretoria | cálculo | fato |
|---|---|---|
| Quanto vendeu (volume e dinheiro) | `SUM(qtd_vendas)`, `SUM(vl_bruto)`, `SUM(vl_liquido)` por `sk_data_ganho` | `ft_venda` |
| Quanto de comissões | `SUM(vl_comissao)` por competência e tipo | `ft_comissao` (ou colunas de comissão em `ft_venda`) |
| Maior valor vendido | `MAX(vl_liquido)` | `ft_venda` |
| Quem mais vendeu em volume | ranking de `SUM(qtd_vendas)` por vendedor/cliente/canal/parceiro | `ft_venda` |
| Margem líquida | `SUM(vl_liquido) / SUM(vl_bruto)`; margem sobre custo: `SUM(vl_margem_custo) / SUM(vl_liquido)` | `ft_venda` |
| Orçamentos realizados (volume e dinheiro) | `COUNT(*)`, `SUM(vl_bruto)`, `SUM(vl_liquido)` por `sk_data_cadastro` | `ft_orcamento` |
| Em aberto, perdidos, ganhos (situação atual) e totais bruto/líquido | `SUM(fl_aberto)`, `SUM(fl_perdido)`, `SUM(fl_ganho)` e as somas de valor condicionadas | `ft_orcamento` |
| Quantos estavam abertos numa data passada | `SUM(qtd_orcamentos)` com `grupo_fase = 'ABERTO'` na posição de fim de mês | `ft_funil_posicao` |
| Taxa de conversão | `SUM(fl_ganho) / COUNT(*)` (definição do relatório vigente) ou `SUM(fl_ganho) / SUM(fl_fechado)` (sobre fechados) | `ft_orcamento` |
| Taxa de perda | `SUM(fl_perdido) / COUNT(*)` ou `/ SUM(fl_fechado)` | `ft_orcamento` |
| Faixa do SLA | a taxa agregada cai na banda de `dim_faixa_sla` (`limite_inferior_exclusivo < taxa*100 <= limite_superior_inclusivo`) | consulta por intervalo |
| Ticket médio, tempo até fechar, motivo da perda | `AVG(vl_liquido)` com `fl_valor_zero = 0`; `AVG(dias_ate_fechar)`; contagem por `sk_motivo_perda` | `ft_venda`, `ft_orcamento` |

## 4. Os ritos executivos no calendário

- **Mensal (agosto de 2026 contra agosto de 2025 e 2024):** filtrar `mes = 8` e `ano IN (2024, 2025, 2026)`; ou, para comparação alinhada dia a dia, juntar a fato duas vezes pelo `sk_data_ano_anterior` e `sk_data_dois_anos_antes`.
- **Semestral (janeiro a julho de cada ano):** `mes BETWEEN 1 AND 7`; a coluna `fl_acumulado_ano_comparavel` marca os dias de cada ano até o dia corrente, para o acumulado comparável.
- **Anual (três anos fechados):** `ano IN (2023, 2024, 2025)`.

Tudo isso se resolve com a dimensão de calendário e as fatos acima, sem uma linha de código no relatório. A régua da gold ([11](11_camada_gold.md)) confere que os totais das fatos batem com a silver e que nenhuma chave está órfã.

---

[Início](#topo)
