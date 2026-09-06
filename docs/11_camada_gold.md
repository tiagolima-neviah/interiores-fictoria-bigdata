<a id="topo"></a>

# Camada Gold: o star schema construído e provado

<!-- nav:start -->
[Home](../README.md) | [← Matriz de Barramento](10_matriz_barramento.md) | [Warehouse Multidimensional →](12_warehouse_multidimensional.md)
<!-- nav:end -->

> A gold materializa a [matriz de barramento](10_matriz_barramento.md): 15 dimensões e 7 fatos em parquet, fatos particionadas por ano. A régua da gold prova, a cada construção, que as fatos batem com a silver, que nenhuma chave está órfã, que a posição do funil fecha com a situação atual e que o arco de conversão continua o da história do negócio.

## 1. Layout

```
data/lake/gold/
├── _controle/construcao_<execucao>.json
├── dim_calendario/parte-000.parquet
├── dim_cliente/parte-000.parquet
├── ... (15 dimensões)
├── ft_orcamento/
│   ├── ano=2021/parte-000.parquet
│   └── ... ano=2026
├── ft_venda/ano=YYYY/...
├── ft_comissao/ano=YYYY/...
├── ft_funil_posicao/ano=YYYY/...
├── ft_orcamento_item/ano=YYYY/...
├── ft_parcela/ano=YYYY/...           # inclui 2027 (parcelas a vencer)
└── ft_follow_up/ano=YYYY/...
```

A partição por ano é a unidade de carga e de auditoria: o warehouse carrega e confere uma a uma, e um destino pequeno (um plano gratuito em nuvem) pode receber só os anos que couberem.

## 2. Números da construção (2026-09-06)

| tabela | linhas | observação |
|---|---|---|
| `dim_calendario` | 2.557 | 2021-01-01 a 2027-12-31 + membro -1 |
| `dim_cliente` | 10.772 | clientes canônicos (12.165 cadastros agrupados) + membro -1 |
| `dim_parceiro` | 622 | 620 parceiros + "Sem parceiro" + "Outros / não cadastrado" |
| `dim_vendedor` | 34 | vendedores, supervisores e projetistas + membro -1 |
| `ft_orcamento` | 14.180 | orçamentos de venda não cancelados |
| `ft_venda` | 3.404 | ganhos |
| `ft_comissao` | 7.595 | |
| `ft_funil_posicao` | 85.530 | 69 posições de fim de mês × dimensões |
| `ft_orcamento_item` | 239.835 | |
| `ft_parcela` | 20.407 | |
| `ft_follow_up` | 46.908 | |

Construção completa em 0,8 s (DuckDB sobre a silver em parquet).

## 3. Decisões de modelagem que valem explicar

- **Chaves substitutas iguais aos ids da origem** onde a entidade é estável (vendedor, parceiro, fase). Simplifica a rastreabilidade num caso didático; num cliente real com histórico de mudança de atributos (vendedor trocando de unidade), a dimensão vira SCD tipo 2 e ganha chave própria.
- **Cliente canônico.** A `dim_cliente` tem uma linha por cliente real (ACH-05); as fatos apontam para o canônico. A quantidade de cadastros agrupados fica na dimensão para quem quiser auditar.
- **Canal e parceiro separados, como a diretoria pede.** `dim_canal.grupo_nome` é a visão consolidada ("outras origens"); `dim_parceiro` é o detalhe. Os totais batem por construção porque vêm da mesma linha da fato.
- **Posição do funil como fato agregada de fim de mês.** Responde "quantos estavam abertos em agosto de 2024, por vendedor" sem carregar 15 mil linhas por mês. A última posição é a data corrente do universo, e a régua confere que ela bate com a situação atual.
- **Flags como 0/1.** `SUM(fl_ganho)` é a contagem de ganhos; `SUM(fl_ganho) / SUM(fl_fechado)` é a conversão. Sem `CASE WHEN` no relatório.
- **SLA como dimensão de bandas.** As faixas da diretoria vivem em `dim_faixa_sla`, aplicadas à taxa agregada por consulta de intervalo. Mudar a régua é editar linhas, e a observação do [docs/01](01_entendimento_negocio.md) sobre a contradição entre conversão e perda continua valendo.

## 4. A régua da gold (43 checks)

- **Reconciliação com a silver:** contagens e somas de `ft_orcamento`, `ft_venda`, `ft_comissao`, `ft_orcamento_item`, `ft_parcela`.
- **Grão:** nenhum `sk_orcamento` duplicado nas fatos de orçamento e venda; nenhuma chave duplicada em cliente e calendário.
- **Integridade dimensional:** 20 pares fato → dimensão sem chave órfã (os membros -1 e -2 fazem parte das dimensões, então "não informado" nunca é órfão).
- **Coerência interna:** aberto sem data de fechamento e fechado com data; posição do funil no último mês igual à situação atual; calendário completo; faixas de SLA contíguas.
- **A história do negócio, lida da gold:** conversão sobre fechados por ano dentro das bandas do plano (as mesmas da régua da origem).

```bash
uv run gold-staging
uv run regua-gold        # esperado: 43 aprovados, 0 reprovados
```

## 5. Consultando a gold direto do parquet

Com DuckDB, sem servidor: o módulo `duck.py` registra as views `g_<tabela>` (`hive_partitioning` lê o `ano` da pasta).

```python
from interiores_fictoria import duck
con, lake = duck.conectar(); duck.registrar_gold(con, lake)
con.sql("""
  SELECT c.ano, SUM(v.qtd_vendas) AS vendas, ROUND(SUM(v.vl_liquido) / 1e6, 1) AS liquido_mi
  FROM g_ft_venda v JOIN g_dim_calendario c ON c.sk_data = v.sk_data_ganho
  GROUP BY 1 ORDER BY 1
""").show()
```

---

[Início](#topo)
