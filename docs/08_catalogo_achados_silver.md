<a id="topo"></a>

# Catálogo de Achados: o contrato da silver

<!-- nav:start -->
[Home](../README.md) | [← Camada Bronze](07_camada_bronze.md) | [Camada Silver →](09_camada_silver.md)
<!-- nav:end -->

> Os notebooks de auditoria ([01 · cadastro e funil](../notebooks/01_qualidade_cadastro_funil.ipynb) e [02 · financeiro e obra](../notebooks/02_qualidade_financeiro_obra.ipynb)) leram o bronze e evidenciaram, um a um, os defeitos e as ambiguidades que um sistema comercial real carrega. Este catálogo consolida cada achado com id estável, taxa observada e a regra que a silver aplica. A silver presta contas contra ele: para cada regra, quantas linhas foram afetadas.

## 1. Princípios

- **Ausência não se preenche.** Quando o dado não existe (CEP, bairro, follow-up), a silver marca e preserva o nulo; a gold ganha um membro "Não informado". Chutar valor é inventar dado.
- **Cabeçalho para valores, trilha para datas.** O total do orçamento é o que a empresa negociou; a trilha de fases é a verdade das datas de fase e fechamento, porque não tem sentinela nem digitação manual.
- **Flag, nunca exclusão.** Linhas problemáticas ficam na silver com a flag do achado; quem exclui é a gold, por regra de negócio explícita (`fl_conta_bi`).
- **Regra reproduzível.** Cada achado tem a consulta que o evidencia (`src/interiores_fictoria/qualidade/achados.py`) e a regra em SQL na silver (`src/interiores_fictoria/silver/transformador.py`).

## 2. Os achados (taxas observadas em 2026-09-06)

| id | achado | observado | regra da silver | onde |
|---|---|---|---|---|
| ACH-01 | Data-sentinela 1900-01-01 no fechamento | 1,95% dos fechados | `dt_fechamento` vem da trilha; `fl_dt_finalizou_sentinela`; registrado preservado em `dt_finalizou_registrado` | `orcamento` |
| ACH-02 | Fechamento anterior ao cadastro | 0,20% dos fechados | `dt_fechamento` pela trilha; `fl_fechou_antes_cadastro`; `dias_ate_fechar` nunca negativo | `orcamento` |
| ACH-03 | Orçamentos de valor zero | 1,35% dos de venda | `fl_valor_zero`; gold exclui das médias de ticket | `orcamento` |
| ACH-04 | Bruto ≠ soma dos itens (item cancelado somado, 2021-2022) | 0,18% dos ativos | `vl_bruto_itens`, `vl_custo_itens`, `qtd_itens`, `fl_divergencia_itens`; gold usa o cabeçalho | `orcamento` |
| ACH-05 | Clientes duplicados por grafia | 11,46% dos cadastros repetem um nome normalizado | `nome_normalizado`, `cliente_canonico_id`, `fl_duplicado_por_grafia`; dim_cliente usa o canônico | `cliente` |
| ACH-06 | Endereços sem CEP ou sem bairro | 13,81% dos endereços | `fl_sem_cep`, `fl_sem_bairro`; bairro do endereço principal vai para o cliente; "Não informado" na gold | `endereco`, `cliente` |
| ACH-07 | Parceiro em texto livre, sem cadastro | 44,94% dos orçamentos do canal Outros | `parceiro_texto_livre` extraído do objetivo; canal permanece OUTROS (parceiro é PJ cadastrada) | `orcamento` |
| ACH-08 | Ganhos sem trilha de execução | 7,73% dos ganhos | `status_operacional` = 'NÃO DEFINIDO'; `fl_sem_trilha_execucao` | `orcamento` |
| ACH-09 | Follow-up ausente depende do vendedor | 16,42% dos orçamentos de venda | `qtd_follow_ups` (zero quando não há); indicador de aderência ao processo, por vendedor | `orcamento` |
| ACH-10 | Fora do escopo do BI: não-venda e cancelados | 7,28% dos orçamentos | `fl_conta_bi` = Venda e não cancelado; a gold só carrega com a flag | `orcamento` |
| ACH-11 | Fase atual × trilha | 100% coerente | trilha é a fonte de datas; cabeçalho, de valores e vínculos | `orcamento_fase_hist` |
| ACH-12 | Comissão com percentual diferente do orçamento | 1,03% das comissões | `p_comissao_esperado`, `fl_comissao_divergente`, `vl_diferenca_esperado` | `comissao` |
| ACH-13 | Parcelas vencidas sem pagamento; pagamentos em atraso | 3,26% das parcelas vencidas sem pagamento | `dt_primeiro_pagamento`, `vl_pago_total`, `fl_vencida_sem_pagamento`, `dias_atraso_pagamento` | `parcela` |
| ACH-14 | Auditoria guarda valores como texto com vírgula | 35.848 alterações monetárias | `vl_antigo_num`, `vl_novo_num` (pt-BR → decimal); `qtd_revisoes` por orçamento | `auditoria_orcamento`, `orcamento` |
| ACH-15 | Ganhos sem recebimento; comissão a apurar | 1,09% dos ganhos sem recebimento | `fl_ganho_sem_recebimento`; comissão "a apurar" resolve-se pelo calendário de competência | `orcamento` |
| ACH-16 | Medições não realizadas; instalações com problema | 15,64% das instalações concluídas com problema | preservado; fatos de obra na gold com as flags | `medicao`, `instalacao` |

## 3. O que a silver acrescenta além dos achados

- `grupo_fase` (ABERTO / GANHO / PERDIDO) direto no orçamento.
- `vl_margem_custo` no orçamento e no item (líquido menos custo dos itens): a margem que a empresa nunca conseguiu ver.
- `fl_atrasada` nas etapas de execução (concluída depois do limite, ou aberta com limite vencido na data corrente do universo).
- `status_nome` e `status_ordem` nas etapas; `categoria_item_id` nos itens.

## 4. Como conferir

```bash
uv run silver-staging
```

A saída lista as linhas afetadas por regra e o resultado das conferências (linha por chave, contagens contra o bronze, soma do bruto preservada, fechados com data pela trilha, nenhum prazo negativo, cliente canônico válido). Qualquer conferência reprovada encerra com código 1: a silver reprova a si mesma antes de a gold consumi-la. O detalhe fica em `silver/_controle/prestacao_contas.json`.

---

[Início](#topo)
