<a id="topo"></a>

# Guia de Reprodução: do clone ao staging validado

<!-- nav:start -->
[Home](../README.md) | [← Régua de Validação](04_regua_validacao.md) | [Carga Incremental →](06_carga_incremental.md)
<!-- nav:end -->

> O manual completo para reproduzir este projeto na sua máquina: pré-requisitos, o passo a passo comentado do clone até o sistema comercial simulado aprovado pela régua e espelhado no staging, verificações de saúde e a solução dos tropeços mais comuns. O gerador é determinístico: seguindo estes passos, você chega **exatamente** aos mesmos números deste documento.

## 1. Pré-requisitos

| requisito | observação |
|---|---|
| Linux (ou WSL2 no Windows) | desenvolvido em Ubuntu 24.04 LTS; no Windows, use WSL2 e trabalhe DENTRO do filesystem Linux (`~/projetos`), nunca em `/mnt/c` |
| Docker + Docker Compose | dois SQL Server 2022 (edição Developer, gratuita para estudo) vivem em containers |
| ODBC Driver 18 for SQL Server + unixODBC | o Python fala com o SQL Server por ODBC; instalação na seção 2 |
| [uv](https://docs.astral.sh/uv/) | gerencia o Python 3.12 e as dependências (ele baixa o Python sozinho se faltar) |
| git | para clonar |
| ~10 GB livres em disco | imagens do SQL Server (~1,6 GB) mais os bancos populados |
| 16 GB de RAM e 4 núcleos | cada SQL Server ocupa cerca de 1,7 GB; 8 GB funciona com um container só |

## 2. Passo a passo

**1. Clone e entre no projeto, SEMPRE no filesystem do Linux:** no WSL, clonar em `/mnt/c/...` funciona, mas degrada muito a performance.

```bash
cd ~
git clone https://github.com/tiagolima-neviah/interiores-fictoria-bigdata.git
cd interiores-fictoria-bigdata
```

**2. Instale o driver ODBC (uma vez por máquina).** No Ubuntu 24.04:

```bash
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -sSL https://packages.microsoft.com/config/ubuntu/24.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y unixodbc msodbcsql18 mssql-tools18
```

O `mssql-tools18` traz o `sqlcmd`, útil para inspecionar os bancos pelo terminal. Em outras distribuições, siga a página oficial de instalação do driver da Microsoft para Linux.

**3. Configure o ambiente (12-factor):** copie o exemplo e defina senhas fortes para os dois SQL Server (o servidor recusa senhas fracas e o container não sobe):

```bash
cp .env.example .env
# edite o .env: MSSQL_SA_PASSWORD e DW_SA_PASSWORD (8+ caracteres, maiúscula, minúscula, dígito e símbolo)
```

**4. Suba os containers:** o serviço `sqlserver` hospeda a origem simulada (`db_fictoria`) e o staging (`stg_fictoria`); o serviço `warehouse` é o segundo SQL Server, vazio até a etapa do multidimensional. O `sqlserver-init` aplica o DDL nos dois bancos e termina.

```bash
cd staging
docker compose --env-file ../.env up -d
docker wait fictoria_sqlserver_init && docker logs fictoria_sqlserver_init | tail -3
cd ..
```

**5. Instale o ambiente Python:**

```bash
uv sync
```

**6. Popule o sistema comercial simulado (o gerador determinístico, menos de um minuto):** o universo inteiro é planejado em memória (cerca de 21 mil orçamentos de 2021 a 2027, com toda a linha do tempo de cada um) e o banco é materializado como ele estaria na data corrente do universo, **4 de setembro de 2026, 18h**. Ao final, cerca de 1,05 milhão de linhas em 30 tabelas.

```bash
uv run gerador-origem
```

**7. Valide com a régua (o contrato de aceite):** 46 verificações. O resultado esperado é `46 aprovados, 0 reprovados`.

```bash
uv run regua-origem
```

**8. Carregue o staging (carga incremental, a primeira é completa):**

```bash
uv run carga-staging
uv run regua-origem --staging   # os mesmos 46 valores: o espelho é fiel
```

**9. Veja a carga incremental funcionar:** rode a carga de novo (nada mudou na origem, nenhuma linha é lida além das marcas d'água), avance o relógio do universo alguns dias e carregue o delta. A mecânica está explicada na [Carga Incremental](06_carga_incremental.md).

```bash
uv run carga-staging                            # 0 linhas lidas
uv run gerador-origem --ate 2026-09-09T12:54    # a "produção" trabalhou 5 dias
uv run carga-staging                            # só o delta
```

Para voltar ao estado canônico (o que os documentos e os próximos capítulos assumem):

```bash
uv run gerador-origem --recriar
uv run carga-staging --recriar
```

## 3. Números de referência (primeira rodada aprovada, 2026-09-06)

| medição | valor |
|---|---|
| Planejamento do universo (2021 a 2027) | 21.387 orçamentos (20.108 de venda), 17.052 clientes, ~12 s |
| Materialização em 04/09/2026 18h | 1.046.564 linhas em 30 tabelas, ~41 s |
| Orçamentos de venda materializados | 15.293 (2021: 1.476 · 2022: 1.711 · 2023: 2.338 · 2024: 2.574 · 2025: 3.525 · 2026 até 04/09: 2.540) |
| Conversão sobre fechados | 2021 8,8% · 2022 14,8% · 2023 18,6% · 2024 25,0% · 2025 31,6% · 2026 (parcial) ~50% |
| Régua da origem | 46 aprovados, 0 reprovados |
| Carga completa do staging | 1.046.564 linhas em 29 s; segunda carga sem mudanças em 0,3 s |
| Avanço do relógio para 09/09/2026 12h54 | 3.760 linhas inseridas, 1.002 atualizadas (44 orçamentos novos); delta carregado no staging em 3,7 s |
| Régua do staging | 46 aprovados, 0 reprovados (mesmos valores da origem) |

## 4. Verificações de saúde

```bash
docker ps --format '{{.Names}} {{.Status}}'          # sqlserver e warehouse "healthy"
docker logs fictoria_sqlserver_init | tail -3          # "DDL aplicado em db_fictoria e stg_fictoria"
uv run gerador-origem --so-planejar                   # planeja e imprime contagens sem tocar o banco
```

Pelo `sqlcmd` (substitua a senha pela do seu `.env`):

```bash
/opt/mssql-tools18/bin/sqlcmd -S localhost,1433 -U sa -P 'SuaSenha' -C -d db_fictoria -Q "SELECT COUNT(*) FROM comercial.orcamento"
```

## 5. Tropeços comuns

| sintoma | causa e solução |
|---|---|
| `Login timeout expired` no Python ou no `sqlcmd` | os containers não estão de pé (reinício do WSL derruba o Docker); `docker compose --env-file ../.env up -d` em `staging/` |
| container do SQL Server reinicia em loop | senha fraca no `.env`; o servidor exige 8+ caracteres com maiúscula, minúscula, dígito e símbolo |
| `libodbc.so.2: cannot open shared object file` | falta o unixODBC/driver 18; refaça o passo 2 |
| `Data source name not found` | o nome do driver difere do padrão; ajuste `ODBC_DRIVER` no `.env` (veja `odbcinst -q -d`) |
| régua reprova depois de mudar `gerador/parametros.py` | o universo mudou e o MERGE tentou casar dois universos diferentes; rode `uv run gerador-origem --recriar` |
| régua do staging "sem dados" | o staging ainda não foi carregado; `uv run carga-staging` |
| `Failed to hardlink files` no `uv sync` | projeto em `/mnt/c`; mova para `~/projetos` |
| SSMS/DBeaver no **Windows** dá timeout em `localhost,1433` (erro 258), mas a porta responde | `localhost` resolve para IPv6 (`::1`) e o relay do WSL2 não completa o handshake do SQL Server por esse caminho; use **`127.0.0.1,1433`** (origem e staging) e **`127.0.0.1,1434`** (warehouse), login `sa`, senha do `.env`, com "Trust server certificate" marcado |

---

[Início](#topo)
