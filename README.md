<a id="topo"></a>

# Fictoria Casa & Interiores · Pipeline de BI comercial ponta a ponta

<!-- nav:start -->
[Entendimento do Negócio](docs/01_entendimento_negocio.md) | [Entendimento dos Dados](docs/02_entendimento_dados.md) | [Modelo de Dados](docs/03_modelo_dados_staging.md)
<!-- nav:end -->

> Pipeline completo e moderno de Business Intelligence construído sobre a **Fictoria Casa & Interiores**, uma empresa **fictícia** de reforma, construção leve e design de interiores para o público de alta renda de São Paulo, com dados **100% sintéticos**: do banco relacional do sistema comercial (SQL Server) ao staging com carga incremental, do staging às camadas bronze, silver e gold em parquet, da gold ao modelo multidimensional (star schema) carregado num warehouse SQL Server, pronto para dashboards web e Power BI. O repositório existe para ajudar analistas em início de carreira a percorrer um projeto de engenharia de dados e BI do jeito que ele acontece no mundo real, com custo baixo e total portabilidade.

> **Aviso:** a Fictoria Casa & Interiores não existe. Empresa, unidades, clientes, parceiros, pessoas, códigos, documentos e valores são fictícios e gerados sinteticamente. Este projeto não possui afiliação com nenhuma empresa real; qualquer semelhança é coincidência.

## ⚠️ Disclaimer: projeto de estudo, não use em produção

Este repositório é um **CASE fictício com dados sintéticos, criado exclusivamente para fins de estudo**. Ele **não deve, em hipótese alguma, ser usado em ambiente de produção real**: por ser material didático, conceitos essenciais de segurança da informação foram deliberadamente deixados de fora do escopo, e códigos, containers e configurações aqui presentes são frágeis por concepção (senhas em `.env` local, serviços sem hardening, ausência de criptografia, controle de acesso e trilha de auditoria).

O software é fornecido **"no estado em que se encontra" (AS IS), sem garantias de qualquer natureza**, nos termos da [licença MIT](LICENSE) deste repositório. Os autores e a Neviah **não se responsabilizam por quaisquer danos** decorrentes do uso deste material; qualquer utilização fora do contexto de estudo, incluindo ambientes produtivos, é feita **por conta e risco exclusivos de quem a fizer**.

Tem interesse em implementar este projeto de verdade na sua empresa? Entre em contato pela **[www.neviah.com.br](https://www.neviah.com.br)**: a implementação real é feita de forma completa e correta, considerando todas as políticas de segurança da informação e de proteção de dados (LGPD).

## Por que este projeto existe

Este é o segundo caso público da série de pipelines de BI da Neviah. O primeiro, a [Fictitur Logística](https://github.com/tiagolima-neviah/logistica-fictitur-bigdata), resolveu um problema de volume e de relatórios que não batiam, sobre Postgres. Este caso muda o segmento, o banco e a pergunta: uma empresa comercial de alto padrão, cujo sistema roda em **SQL Server**, que **não tem nenhum relatório confiável da área comercial** e cuja única tentativa de BI travava o sistema de vendas sempre que atualizava. A arquitetura é a mesma da série, portável e de baixo custo: SQL Server em container, Python, parquet e Docker, com storage abstraído para rodar no notebook do analista, num servidor da empresa ou na nuvem, sem reescrever o pipeline.

## O caso

A Fictoria Casa & Interiores nasceu em 2021 num showroom nos Jardins e hoje tem **3 unidades** em São Paulo e **22 vendedores**. Faz projeto, reforma, marcenaria planejada, acabamentos de alto padrão, cortinas e proteção solar, e entrega a obra instalada. Grande parte dos orçamentos chega por **escritórios de arquitetura e construtoras parceiras**, que recebem comissão; o resto vem dos canais próprios (WhatsApp, Instagram, Facebook, SAC do showroom) e de indicações de clientes.

A dor declarada pela diretoria: **não existe relatório capaz de dizer quanto se vendeu, quanto se pagou de comissão, quantos orçamentos estão abertos, ganhos e perdidos, qual a taxa de conversão e como tudo isso evolui por vendedor, cliente, canal e parceiro**. A empresa tem um SLA de conversão (crítico, ruim, regular, boa, excelente) e nenhuma estrutura de dados para medi-lo. A tentativa anterior de BI lia direto do banco de produção e deixava o sistema quase inoperante durante a atualização, e foi desligada. A solução contratada: um **staging** que espelha o banco do sistema comercial com **carga incremental diária** (a produção respira) e um pipeline analítico que reconstrói os indicadores comerciais de uma única fonte da verdade, com histórico, comparativos entre anos e as faixas de SLA. A história completa está no [Entendimento do Negócio](docs/01_entendimento_negocio.md).

## Arquitetura

```
Sistema comercial da Fictoria (db_fictoria, SQL Server em Docker, simulado)
        │  carga incremental diária (marca d'água rowversion por tabela)
        ▼
Staging (stg_fictoria, mesmo SQL Server, 4 schemas, 30 tabelas)
        ▼
Bronze ──► Silver ──► Gold (parquet; storage via fsspec: file:// ↔ s3://)
                        ▼
              Star schema multidimensional
                        ▼
     Warehouse (SQL Server em Docker) e destino em nuvem configurável por .env
                        ▼
            Dashboards web e Power BI
```

Os notebooks acompanham a esteira como referência de método: auditoria de qualidade do bronze (o que a silver precisa tratar), demonstração e teste do modelo multidimensional (as perguntas do executivo respondidas pelo star schema).

## Status do projeto

| etapa | situação |
|---|---|
| Entendimento do negócio e dos dados | concluído |
| Modelo relacional + DDL T-SQL (staging) | concluído |
| SQL Server no Docker (origem simulada + staging) com o DDL aplicado | concluído |
| Régua de validação dos dados sintéticos | a iniciar |
| Gerador de dados sintéticos (2021 a 04/09/2026) | a iniciar |
| Carga incremental diária (staging) | a iniciar |
| Bronze (staging → parquet via fsspec) | a iniciar |
| Auditoria de qualidade (notebooks) + catálogo de regras da silver | a iniciar |
| Silver (regras aprovadas + prestação de contas) | a iniciar |
| Matriz de barramento + Gold (star schema particionado por ano) | a iniciar |
| Warehouse multidimensional SQL Server + carga por partição | a iniciar |
| Notebook de testes do modelo multidimensional | a iniciar |
| Carga no destino em nuvem | a iniciar |
| Dashboards | outro projeto |

## Requisitos

**Máquina (estimativa, a consolidar):** 16 GB de RAM (dois SQL Server em container pedem cerca de 2 GB cada), 4 núcleos, ~20 GB livres em disco.

**Sistema:** o projeto é desenvolvido em **Ubuntu 24.04 LTS** (via WSL2 no Windows 11). Usuários de Windows devem usar o **WSL2**; usuários de Linux/macOS rodam nativo (no macOS com Apple Silicon o SQL Server roda em emulação). Ferramentas: **Docker + Docker Compose**, **Python 3.12**, **git**, o **ODBC Driver 18 for SQL Server** (o guia de reprodução mostra como instalar). Recomendado: [uv](https://docs.astral.sh/uv/) para o ambiente Python e um cliente SQL (DBeaver, Azure Data Studio, `sqlcmd`).

**Conhecimentos que ajudam:** SQL, Python básico, noções de Docker e terminal Linux. Cada etapa da documentação explica o que faz e por quê; o objetivo é que um analista em formação consiga acompanhar.

## Como rodar (estado atual)

O staging ainda não está publicado; o quickstart abaixo é o alvo do projeto e é atualizado a cada etapa concluída.

```bash
cd ~                        # SEMPRE no filesystem do Linux; /mnt/c degrada muito a performance
git clone https://github.com/tiagolima-neviah/interiores-fictoria-bigdata.git
cd interiores-fictoria-bigdata
cp .env.example .env        # edite as senhas (o SQL Server exige senha forte)
cd staging && docker compose --env-file ../.env up -d && cd ..
uv sync
uv run gerador-staging      # popula o sistema comercial simulado, 2021 a 04/09/2026 (determinístico)
uv run regua-staging        # valida: o contrato de aceite dos dados sintéticos
uv run carga-staging        # carga incremental: origem → staging por marca d'água
uv run bronze-staging       # lake: staging → parquet com verificação de contagens
uv run silver-staging       # regras do catálogo + prestação de contas
uv run gold-staging         # star schema: dimensões + fatos particionadas por ano
uv run regua-gold           # valida a gold contra a silver e contra a história
uv run carga-dw             # gold → warehouse SQL Server (porta 1434), partição a partição
uv run carga-dw --env .env.nuvem   # opcional: o mesmo, para um destino em nuvem
```

## Estrutura de diretórios

```
interiores-fictoria-bigdata/
├── README.md            # este hub
├── LICENSE              # MIT (software fornecido AS IS, sem garantias)
├── .env.example         # configuração 12-factor (copie para .env; o .env não é versionado)
├── pyproject.toml       # pacote Python + esteira de qualidade (ruff, mypy, pytest)
├── docs/                # documentação do projeto (negócio, dados, manuais)
├── notebooks/           # auditoria de qualidade e testes do multidimensional (quando existirem)
├── src/interiores_fictoria/
│   └── config.py        # configuração 12-factor (conexões e lake vêm do ambiente)
├── tests/               # testes da esteira de qualidade
└── staging/
    ├── docker-compose.yml   # SQL Server (origem simulada + staging) e SQL Server do warehouse
    └── ddl/                 # DDL T-SQL dos 4 schemas e 30 tabelas (00..04), idempotente
```

## Documentação

<details open>
<summary><strong>Regras de negócio e documentação técnica</strong> (leia na ordem)</summary>

**Fundação**

- [01 · Entendimento do Negócio](docs/01_entendimento_negocio.md): quem é a Fictoria, como vende, as dores, os indicadores e o SLA de conversão que o pipeline precisa entregar.
- [02 · Entendimento dos Dados](docs/02_entendimento_dados.md): os 4 schemas e o papel de cada grupo de tabelas, em linguagem de negócio.
- [03 · Modelo de Dados do Staging](docs/03_modelo_dados_staging.md): a referência técnica, com o diagrama e o objetivo de cada uma das 30 tabelas.

Os próximos documentos nascem com as etapas: régua de validação, guia de reprodução, camadas bronze, silver e gold, matriz de barramento, warehouse multidimensional e warehouse na nuvem.

</details>

---

[Início](#topo)
