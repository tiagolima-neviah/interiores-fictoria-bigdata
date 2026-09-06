<a id="topo"></a>

# Warehouse Multidimensional: a gold servida em SQL Server

<!-- nav:start -->
[Home](../README.md) | [← Camada Gold](11_camada_gold.md)
<!-- nav:end -->

> O star schema em parquet é ótimo para o analista com DuckDB; o dashboard e o Power BI querem um banco. O warehouse é o segundo SQL Server do compose, com o schema `dw` carregado a partir da gold, partição a partição, com prestação de contas. É o destino local; um destino em nuvem usa o mesmo carregador apontado por `.env` (fora do escopo desta versão).

## 1. O que o carregador faz

1. Cria o banco (`dw_fictoria`, collation UTF-8) e o schema `dw` se não existirem.
2. **Dimensões:** recria a tabela a partir do esquema do parquet (tipos Arrow → T-SQL; texto dimensionado pelo maior valor observado), com chave primária clusterizada na `sk_*` quando ela é única, e insere tudo (são pequenas).
3. **Fatos:** cria a tabela na primeira vez com **índice columnstore clusterizado** (o formato colunar é o certo para varreduras analíticas e compacta muito) e, para cada ano em `DW_ANOS` (vazio = todos), apaga a partição e insere as linhas do parquet. Idempotente por partição.
4. **Prestação de contas:** para cada partição, linhas no parquet × linhas na tabela; qualquer divergência encerra com erro. O manifesto vai para `gold/_controle/carga_dw_<execução>.json`.

```bash
uv run carga-dw                    # container local (porta 1434)
DW_ANOS=2025,2026 uv run carga-dw  # só as partições recentes
uv run carga-dw --env .env.nuvem   # um destino externo por DW_URL (quando houver)
```

## 2. Números de referência (2026-09-06)

| medição | valor |
|---|---|
| Carga completa (15 dimensões + 7 fatos, 417.859 linhas de fato) | 8,8 s |
| Tamanho do schema `dw` | 4,5 MB (columnstore) |
| Prestação de contas | 43 partições, todas iguais ao parquet |

Para comparar: a mesma informação ocupa ~1,05 milhão de linhas relacionais na origem. O star schema entrega as respostas da diretoria com menos de meio milhão de linhas e uma fração do espaço.

## 3. Conectando

Qualquer cliente SQL Server chega no warehouse: DBeaver, Azure Data Studio, `sqlcmd` (`-S localhost,1434 -d dw_fictoria`), Power BI Desktop (conector SQL Server, modo Import ou DirectQuery). Uma consulta típica do rito mensal:

```sql
SELECT c.ano, c.nome_mes, SUM(v.qtd_vendas) AS vendas, SUM(v.vl_liquido) AS liquido,
       SUM(v.vl_comissao_total) AS comissoes
FROM dw.ft_venda v
JOIN dw.dim_calendario c ON c.sk_data = v.sk_data_ganho
WHERE c.mes = 8 AND c.ano IN (2024, 2025, 2026)
GROUP BY c.ano, c.nome_mes ORDER BY c.ano;
```

E a régua de SLA aplicada por consulta de intervalo:

```sql
WITH t AS (
  SELECT c.ano, 100.0 * SUM(o.fl_ganho) / SUM(o.fl_fechado) AS conversao
  FROM dw.ft_orcamento o JOIN dw.dim_calendario c ON c.sk_data = o.sk_data_cadastro
  WHERE o.fl_fechado = 1 GROUP BY c.ano)
SELECT t.ano, t.conversao, s.faixa
FROM t JOIN dw.dim_faixa_sla s ON s.tipo = 'CONVERSAO'
  AND t.conversao > s.limite_inferior_exclusivo AND t.conversao <= s.limite_superior_inclusivo
ORDER BY t.ano;
```

## 4. Os notebooks que provam o modelo

- [03 · Avaliação do modelo multidimensional](../notebooks/03_avaliacao_modelo_multidimensional.ipynb): cardinalidades, membros especiais, grão e partições das fatos, integridade referencial no warehouse, posição do funil × situação atual.
- [04 · Testes de indicadores](../notebooks/04_testes_indicadores.ipynb): cada indicador da diretoria calculado no warehouse e recalculado direto na origem (SQL Server transacional) com as regras de negócio; a diferença tem de ser zero. Fecha com os ritos executivos (mensal, semestral, anual) desenhados a partir do warehouse.

Ambos são gerados e executados por `uv run notebooks-modelo`.

## 5. O que fica para a próxima versão

Destino em nuvem (Azure SQL na oferta gratuita, ou Postgres/Neon pelo mesmo carregador), agendamento diário do `pipeline` e o dashboard web sobre este warehouse, que é outro projeto.

---

[Início](#topo)
