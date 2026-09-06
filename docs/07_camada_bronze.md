<a id="topo"></a>

# Camada Bronze: o staging congelado em parquet

<!-- nav:start -->
[Home](../README.md) | [← Carga Incremental](06_carga_incremental.md) | [Catálogo de Achados →](08_catalogo_achados_silver.md)
<!-- nav:end -->

> O bronze é a primeira camada do lake: o staging copiado para parquet, carga a carga, sem nenhuma transformação. É intocável por doutrina: o que entrou nunca é alterado, e qualquer leitura pode ser refeita a partir dele. Storage plugável via fsspec (`LAKE_URL`: `data/lake` local hoje, `s3://` amanhã, sem mudar o código).

## 1. Layout

```
data/lake/bronze/
├── _controle/
│   ├── marcas.json                 # por tabela, o maior _rv_origem já copiado
│   └── cargas/<execucao>.json      # manifesto de linhagem de cada execução
├── cadastro.cliente/
│   └── carga=20260906T200538/parte-000.parquet
├── comercial.orcamento/
│   └── carga=20260906T200538/parte-000.parquet
└── ... (30 tabelas)
```

Uma pasta `carga=<execução>` por rodada que trouxe linhas: a primeira carga traz tudo, as seguintes só o delta (o mesmo mecanismo de marca d'água do staging, agora sobre `_rv_origem`). A mesma chave pode aparecer em várias cargas, cada uma com a versão daquela data; quem monta o estado corrente é a silver (maior `_rv_origem` vence). Isso preserva o histórico de versões de graça.

## 2. Esquema explícito, não inferido

Os tipos do parquet vêm do `INFORMATION_SCHEMA` do staging, mapeados para Arrow (`bigint` → int64, `decimal(p,s)` → decimal128, `datetime2` → timestamp, `bit` → bool...). Inferir tipos de uma amostra funciona até a primeira carga em que uma coluna vem toda nula; com esquema explícito, os arquivos de cargas diferentes têm sempre o mesmo formato e podem ser lidos juntos (`union_by_name`).

## 3. Linhagem e conferência

Cada execução escreve um manifesto com, por tabela: linhas lidas, linhas gravadas, marca anterior e nova, total no staging e total acumulado no bronze, tempo. A conferência reprova a execução se o total acumulado no bronze for menor que o do staging. A leitura de contagem do parquet é feita pelos metadados do arquivo, sem varrer os dados.

## 4. Números de referência (2026-09-06)

| medição | valor |
|---|---|
| Primeira carga | 1.046.564 linhas, 30 tabelas, 7,5 s |
| Segunda carga, staging inalterado | 0 linhas novas, 0,1 s |
| Maiores tabelas | `auditoria_orcamento` 389.390 · `orcamento_item` 258.438 · `orcamento_historico` 126.061 |

## 5. Como rodar

```bash
uv run bronze-staging
```

O comando é idempotente: sem novidade no staging, registra um manifesto vazio e termina. A leitura do bronze em qualquer ferramenta usa o padrão `bronze/<tabela>/carga=*/*.parquet` com particionamento hive; os notebooks de auditoria e a silver leem pelas views `b_<tabela>` do módulo `duck.py`, que já entregam o estado corrente por chave.

---

[Início](#topo)
