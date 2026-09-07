<a id="topo"></a>

# Camada Silver: o bronze conformado, com prestação de contas

<!-- nav:start -->
[Home](../README.md) | [← Catálogo de Achados](08_catalogo_achados_silver.md) | [Matriz de Barramento →](10_matriz_barramento.md)
<!-- nav:end -->

> A silver é o estado corrente de cada entidade, limpo pelas regras do catálogo de achados e enriquecido com o que o negócio precisa e o sistema não entrega pronto: data de fechamento confiável, cliente canônico, margem sobre custo, status operacional, contagem de follow-ups e revisões. Ela presta contas ao final: quantas linhas cada regra afetou e um conjunto de conferências que reprova a execução quando a silver não bate com o bronze.

## 1. Do bronze à silver

O bronze guarda versões (uma pasta por carga); a silver reduz ao **estado corrente por chave**: para cada `id`, a linha com maior `_rv_origem` (o `rowversion` da origem). Isso vale para as 30 tabelas. Vinte e duas passam por essa redução e nada mais (catálogos, follow-up, histórico, recebimento, pagamento, obra, trilha de fases); oito recebem regras:

| tabela | o que a silver acrescenta |
|---|---|
| `cliente` | `nome_normalizado`, `cliente_canonico_id`, `fl_duplicado_por_grafia` (ACH-05); bairro, cidade e UF do endereço principal, `fl_sem_bairro` (ACH-06) |
| `endereco` | `fl_sem_cep`, `fl_sem_bairro` (ACH-06) |
| `orcamento` | `grupo_fase`; `fl_conta_bi` (ACH-10); `dt_fechamento` e `dias_ate_fechar` pela trilha, com `dt_finalizou_registrado`, `fl_dt_finalizou_sentinela`, `fl_fechou_antes_cadastro` (ACH-01/02/11); `fl_valor_zero` (ACH-03); `vl_bruto_itens`, `vl_custo_itens`, `qtd_itens`, `fl_divergencia_itens` (ACH-04); `parceiro_texto_livre` (ACH-07); `status_operacional`, `fl_sem_trilha_execucao` (ACH-08); `qtd_follow_ups` (ACH-09); `qtd_revisoes` (ACH-14); `fl_ganho_sem_recebimento` (ACH-15); `vl_margem_custo` |
| `orcamento_item` | `fl_cancelado`, `categoria_item_id`, `vl_margem_custo` |
| `orcamento_etapa` | `status_nome`, `status_ordem`, `fl_atrasada` |
| `auditoria_orcamento` | `vl_antigo_num`, `vl_novo_num` (ACH-14) |
| `parcela` | `dt_primeiro_pagamento`, `vl_pago_total`, `fl_vencida_sem_pagamento`, `dias_atraso_pagamento` (ACH-13) |
| `comissao` | `p_comissao_esperado`, `fl_comissao_divergente`, `vl_diferenca_esperado` (ACH-12) |

A regra de cada coluna está no catálogo ([08](08_catalogo_achados_silver.md)); a implementação, em SQL DuckDB, está em `src/interiores_fictoria/silver/transformador.py`, uma consulta por tabela.

## 2. Layout

```
data/lake/silver/
├── _controle/prestacao_contas.json
├── orcamento/parte-000.parquet
├── cliente/parte-000.parquet
└── ... (30 tabelas, uma pasta cada)
```

A silver é reconstruída por inteiro a cada execução (é barata: menos de um segundo) e representa sempre o estado corrente. Quem precisa de história de versões tem o bronze.

## 3. Prestação de contas (rodada de referência, 2026-09-06)

| regra | linhas afetadas |
|---|---|
| ACH-01 fechamentos com data-sentinela substituída pela trilha | 276 |
| ACH-02 fechamentos anteriores ao cadastro substituídos pela trilha | 29 |
| ACH-03 orçamentos de valor zero sinalizados | 215 |
| ACH-04 bruto divergente dos itens sinalizados | 28 |
| ACH-05 clientes apontados para um cadastro canônico | 1.394 |
| ACH-06 endereços sem CEP ou sem bairro (preservados) | 1.931 |
| ACH-07 parceiro em texto livre extraído | 228 |
| ACH-08 ganhos sem trilha de execução | 462 |
| ACH-09 orçamentos de venda sem follow-up | 2.328 |
| ACH-10 fora do escopo do BI (não-venda ou cancelados) | 1.113 |
| ACH-12 comissões com percentual divergente | 66 |
| ACH-13 parcelas vencidas sem pagamento | 665 |
| ACH-14 alterações monetárias convertidas para número | 35.848 |
| ACH-15 ganhos sem recebimento | 236 |

Dez conferências reprovam a execução se falharem: uma linha por chave; contagens iguais ao bronze (orçamento e itens); soma do bruto preservada; todo fechado com data pela trilha e nenhum aberto com data; nenhum prazo negativo; cliente canônico existente e mínimo do grupo; `fl_conta_bi` igual à regra aplicada no bronze; toda comissão com orçamento. Rodada de referência: 10/10 em 0,9 s.

## 4. Como rodar

```bash
uv run silver-staging
```

---

[Início](#topo)
