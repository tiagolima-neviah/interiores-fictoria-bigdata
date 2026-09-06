<a id="topo"></a>

# Carga Incremental: o staging que não pesa na produção

<!-- nav:start -->
[Home](../README.md) | [← Guia de Reprodução](05_guia_reproducao.md)
<!-- nav:end -->

> A dor número três da Fictoria era um BI que lia direto do banco de produção e travava o sistema de vendas a cada atualização. Este capítulo mostra a solução: um staging que espelha o sistema comercial lendo, a cada carga, **só as linhas que mudaram**, com a prova em números. Mostra também como o universo sintético "continua trabalhando" para a demonstração fazer sentido.

## 1. A mecânica: marca d'água por `rowversion`

Toda tabela da origem tem uma coluna `rv` do tipo `rowversion`: um contador de 8 bytes que o SQL Server incrementa, para o banco inteiro, a cada gravação de linha. Quem grava não precisa fazer nada; quem lê ganha um relógio lógico monotônico. O carregador (`uv run carga-staging`) faz, para cada uma das 30 tabelas, pais antes de filhos:

1. Lê no staging a **marca d'água** da tabela (o maior `rv` já carregado; zero na primeira vez).
2. Consulta na origem apenas `WHERE rv > marca`, ordenado por `rv`, usando o índice sobre `rv` nas tabelas grandes.
3. Aplica as linhas no staging por **MERGE** sobre a chave primária: nova é inserida, alterada é atualizada, igual não é tocada.
4. Avança a marca para o maior `rv` lido e registra a execução em `controle.carga` (linhas lidas, inseridas, atualizadas, marcas anterior e nova, tempo).

O staging tem as mesmas 30 tabelas da origem (mesmo DDL) e três colunas de controle por tabela, criadas pelo carregador na primeira execução: `_carregado_em` (quando a linha entrou ou foi atualizada no staging), `_origem` (de qual banco veio) e `_rv_origem` (o `rowversion` da origem, convertido para `bigint`, que é a própria marca d'água). Cancelamentos na origem são lógicos (datas de cancelamento), então não há exclusão física a perseguir; se um dia houver, a resposta clássica é uma tabela de tombstones ou o Change Tracking do SQL Server.

Por que não datas de atualização? Porque `dt_atualizacao` depende de o sistema preenchê-la sempre e do relógio do servidor; o `rowversion` é mantido pelo motor e nunca falha. A origem carrega as duas, e o pipeline usa a segunda como verdade.

## 2. O relógio do universo

O gerador não "insere dados": ele **materializa o banco como ele estaria num instante T**. O universo inteiro (2021 até o fim de 2027) é planejado em memória a partir de uma semente fixa, cada orçamento com sua linha do tempo completa; depois, para cada tabela, o gerador calcula as linhas como de T e as sincroniza por MERGE. A data corrente canônica é **04/09/2026 18h**.

```bash
uv run gerador-origem                          # materializa como de 04/09/2026 18h (estado canônico)
uv run gerador-origem --ate 2026-09-09T12:54   # a produção "trabalhou" mais cinco dias
uv run gerador-origem --agora                  # T = relógio da sua máquina
uv run gerador-origem --recriar                # zera a origem e volta ao canônico
```

Avançar o relógio faz exatamente o que uma produção real faria naqueles dias: orçamentos novos são cadastrados, fases avançam, etapas são concluídas, parcelas são pagas, comissões são liberadas, instalações terminam. Como o MERGE só grava o que difere, **apenas essas linhas ganham um `rowversion` novo**, e a carga seguinte do staging lê só elas. Rodar de novo com o mesmo T não altera nada: nem linhas, nem `rowversion`.

## 3. A prova em números (rodada de referência, 2026-09-06)

| passo | linhas lidas da origem | inseridas no staging | atualizadas | tempo |
|---|---|---|---|---|
| Carga completa (primeira vez) | 1.046.564 | 1.046.564 | 0 | 29 s |
| Segunda carga, nada mudou | **0** | 0 | 0 | 0,3 s: só as 30 marcas foram consultadas |
| Origem avançada de 04/09 para 09/09 12h54 | 4.762 | 3.760 | 1.002 | 3,7 s |

Em cinco dias de operação a produção gerou 44 orçamentos novos, 153 orçamentos mudaram de fase ou fecharam, 105 parcelas novas e 112 quitadas, 28 instalações abertas e 51 atualizadas. A carga incremental leu 4.762 linhas de um banco com mais de um milhão: **0,45%**. Esse é o número que responde à diretoria da Fictoria.

A régua de validação roda também contra o staging (`uv run regua-origem --staging`) e devolve os mesmos 46 valores da origem: o espelho é fiel por construção.

## 4. Onde isso se encaixa no pipeline

O staging é a fonte do bronze. A partir daqui, o pipeline analítico (bronze → silver → gold) lê do staging, nunca da produção, e pode rodar quantas vezes quiser sem tocar no sistema de vendas. A próxima etapa, a camada bronze, congela o staging em parquet com linhagem e verificação de contagens.

---

[Início](#topo)
