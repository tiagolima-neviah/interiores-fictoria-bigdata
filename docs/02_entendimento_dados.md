<a id="topo"></a>

# Entendimento dos Dados: o banco do sistema comercial da Fictoria

<!-- nav:start -->
[Home](../README.md) | [← Entendimento do Negócio](01_entendimento_negocio.md) | [Modelo de Dados →](03_modelo_dados_staging.md)
<!-- nav:end -->

> O mapa do banco `db_fictoria`: 4 schemas e 30 tabelas que representam o sistema comercial da empresa (o "ERP de vendas" que os vendedores usam todo dia), espelhado no staging com carga incremental diária. O DDL completo e comentado está em [`staging/ddl/`](../staging/ddl/); este documento explica o papel de cada grupo de tabelas e as regras que o pipeline precisa conhecer.

## 1. Visão geral

| schema | papel | tabelas |
|---|---|---|
| `cadastro` | entidades mestres e parametrização: unidades, pessoas, clientes, parceiros, catálogo e catálogos de domínio | 16 |
| `comercial` | o funil: orçamento, itens, trilha de fases, etapas de execução, follow-up, histórico e auditoria | 7 |
| `financeiro` | recebimentos, parcelas, pagamentos e comissões | 4 |
| `obra` | a execução do que foi vendido: medição, instalação e histórico | 3 |

O detalhamento técnico, com o diagrama do modelo e o objetivo de cada uma das 30 tabelas, está no [Modelo de Dados do Staging](03_modelo_dados_staging.md).

## 2. `cadastro`: quem é quem e as regras do jogo

- **`unidade`** são os showrooms (Jardins desde 2021, Itaim desde 2023, Alto de Pinheiros desde 2025). Vendedor, cliente e orçamento apontam para uma unidade.
- **`usuario`** é quem opera o sistema: vendedores, supervisores, projetistas 3D, medidores, instaladores e gestão. Um usuário acumula papéis por flags; datas de admissão e desligamento contam a história da equipe (7 vendedores em 2021, 22 em 2026).
- **`origem_contato`** é o **canal** por onde um orçamento chega. O campo `grupo` carrega a leitura consolidada que a diretoria chama de "outras origens": canal próprio, indicação de cliente, arquitetos, construtoras, outros.
- **`parceiro`** são os escritórios de arquitetura e as construtoras. Sempre pessoa jurídica, com percentual de comissão padrão e o vendedor que cuida do relacionamento.
- **`cliente`** guarda o canal do **primeiro** contato e quem indicou (outro cliente ou um parceiro). É por aqui que "cliente reincidente" e "indicação de cliente" se calculam. **`endereco`** separa residência, obra, litoral, campo e comercial.
- **`fase`** (o funil, com `grupo` ABERTO/GANHO/PERDIDO), **`status_etapa`** (a execução, com prazo em dias), **`motivo_perda`**, **`tipo_orcamento`** (só VENDA conta no BI), **`ambiente`**, **`categoria_item`**, **`forma_pagamento`** e **`condicao_parcelamento`** são catálogos de domínio.
- **`item_catalogo`** e **`fornecedor`**: o que se vende, de quem se compra, com valor e custo de referência.

## 3. `comercial`: o funil acontecendo

- **`orcamento`** é a entidade central: cliente, unidade, vendedor, canal, parceiro, fase atual, datas de cadastro e de fechamento, totais bruto, desconto e líquido, percentuais e valores de comissão. Um orçamento cancelado (`dt_cancelou`) sai de todas as contas; uma revisão aponta para o original em `orcamento_ref_id`.
- **`orcamento_item`**: cada produto ou serviço, num ambiente, com quantidade, valor praticado e custo. Os totais do orçamento são a soma dos itens não cancelados (a régua confere).
- **`orcamento_fase_hist`** é a **trilha de fases**: cada passagem registra entrada e saída, e a linha sem saída é a fase atual. É esta tabela que permite reconstruir quantos orçamentos estavam em aberto em qualquer data do passado, coisa que o snapshot atual não responde. A tentativa de BI anterior não a usava, e por isso só conseguia mostrar a foto de hoje.
- **`orcamento_etapa`** registra as etapas de execução depois do ganho, com prazo-limite e conclusão; a etapa aberta é o status operacional atual. Muitos orçamentos (os perdidos e os abertos) não têm etapa alguma, e o status deles é legitimamente "não definido".
- **`follow_up`**, **`orcamento_historico`** e **`auditoria_orcamento`** são as trilhas de interação e mudança: contatos com o cliente, ações registradas e o antes/depois de cada campo alterado. A auditoria conta revisões comerciais (cada alteração de valor líquido é uma renegociação).

## 4. `financeiro` e `obra`: depois do ganho

- **`recebimento`** é o contrato de pagamento de um orçamento ganho; **`parcela`** e **`pagamento`** detalham vencimentos e quitações. A data do primeiro pagamento é o marco que libera a comissão.
- **`comissao`** apura, por orçamento ganho, a comissão do vendedor, do parceiro (reserva técnica), do projetista 3D e do supervisor, por competência, com data de pagamento.
- **`medicao`**, **`instalacao`** e **`instalacao_historico`** contam a obra: medição agendada e realizada, instalação prevista, iniciada e concluída, problemas e a aprovação do pós-venda.

## 5. Como o staging espelha este banco

O sistema comercial (`db_fictoria`) e o staging (`stg_fictoria`) vivem no mesmo SQL Server em container, como bancos separados. Toda tabela de negócio carrega `dt_atualizacao` e `rv` (um `rowversion`, o contador que o SQL Server incrementa a cada gravação). A carga incremental diária lê de cada tabela apenas as linhas com `rv` maior que a marca d'água da carga anterior, grava no staging com as colunas de controle `_carregado_em` e `_origem`, e avança a marca. Cancelamentos são lógicos (datas de cancelamento), então não há exclusão física a perseguir. É esta mecânica que tira o peso do BI de cima da produção: a leitura diária toca só o que mudou.

## 6. O que esperar da qualidade destes dados

O gerador sintético reproduz, de propósito e em taxa calibrada, a sujeira que um sistema comercial real carrega: datas-sentinela (1900-01-01) em campos de fechamento, orçamentos fechados antes de cadastrados (relógio de estação errado), orçamentos de valor zero, clientes duplicados por grafia, CEP e bairro faltantes, parceiro informado como texto livre sem cadastro, status de etapa ausente na maioria dos orçamentos, auditoria com valores antigos e novos como texto, e follow-up inconsistente (vendedores que registram tudo e vendedores que não registram nada). O catálogo completo, com as taxas planejadas e o tratamento de cada caso, vira o contrato da camada silver.

---

[Início](#topo)
