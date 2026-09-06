<a id="topo"></a>

# Entendimento do Negócio: Fictoria Casa & Interiores

<!-- nav:start -->
[Home](../README.md) | [Entendimento dos Dados →](02_entendimento_dados.md)
<!-- nav:end -->

> Quem é a empresa fictícia deste caso, como ela vende, que dores motivaram o projeto, quais indicadores a diretoria precisa enxergar e o que o pipeline entrega. Este documento é a porta de entrada: quem entende o negócio lê os dados com outros olhos.

## 1. A empresa

A **Fictoria Casa & Interiores** é uma empresa de **reforma, construção leve e design de interiores** para o público de alta renda de São Paulo. Nasceu em 2021 num showroom nos Jardins e hoje opera **3 unidades** (Jardins, Itaim Bibi e Alto de Pinheiros), atendendo residências e imóveis comerciais nos bairros do Jardim Europa para cima: Jardim América, Cidade Jardim, Itaim, Vila Nova Conceição, Alto de Pinheiros, Morumbi, mais casas de litoral (Guarujá, Riviera) e de campo (Itu, Bragança, Atibaia).

Ela entrega o ambiente pronto, e não produtos soltos. Quatro frentes se completam num mesmo orçamento:

- **Projeto e obra:** projeto de interiores com apresentação em 3D, gerenciamento da reforma, marcenaria planejada e mão de obra especializada.
- **Acabamentos de alto padrão:** pedras naturais, porcelanatos, pisos, louças e metais de marcas premium.
- **Cortinas e proteção solar:** cortinas, persianas, rolôs e romanas para os interiores; pérgolas, coberturas retráteis e toldos para varandas e áreas externas.
- **Instalação e pós-venda:** equipe própria de medição e instalação, com assistência técnica depois da entrega.

O ticket é alto e disperso: metade dos orçamentos fica abaixo de R$ 70 mil, mas os maiores passam de R$ 1 milhão, e uma única venda grande muda o mês de um vendedor.

## 2. Como um orçamento vive

O funil comercial da Fictoria tem sete fases, agrupadas em três leituras que o negócio usa o tempo todo:

| grupo | fases | o que acontece |
|---|---|---|
| **Em aberto** | Agendar visita ao showroom · Visita local com medidor técnico · Mapeamento das necessidades · Em andamento (proposta e projeto 3D) · Negociação | o cliente chegou por um canal, foi atendido por um vendedor, teve o local medido, recebeu proposta e negocia |
| **Ganho** | Fechado/Ganho | proposta aceita: nasce o contrato de recebimento, a comissão e a execução da obra |
| **Perdido** | Fechado/Perdido | proposta recusada, adiada ou sem retorno, com o motivo registrado |

Depois do ganho, o orçamento entra nas **etapas de execução**: medição final, projeto e produção, cotação e compras com fornecedores, planejamento, instalação, correções e a aprovação do pós-venda, até ser finalizado. Cada etapa tem um prazo-padrão em dias, e o sistema registra quando cada uma foi cadastrada e concluída.

Regras que o BI precisa respeitar:

- **Só orçamentos do tipo Venda contam** para os indicadores comerciais. Assistência técnica, garantia e cortesia existem no sistema e são filtrados.
- **Data de cadastro e data de fechamento são eixos diferentes.** "Quantos orçamentos foram feitos em agosto" usa a data de cadastro; "quanto vendemos em agosto" usa a data do ganho. Um orçamento cadastrado em junho e ganho em agosto conta nos dois lugares, cada um no seu eixo.
- **Um orçamento cancelado sai de todas as contas.**
- **Revisões** (nova versão do mesmo orçamento) apontam para o orçamento original e não duplicam a contagem.

## 3. Canais e parceiros

Todo orçamento tem um **canal de entrada** e, quando veio de indicação profissional, um **parceiro**.

**Parceiros** são sempre pessoas jurídicas: **escritórios de arquitetura** e **construtoras**. Eles trazem o cliente, acompanham o projeto e recebem comissão (a reserva técnica) sobre o que for vendido. Arquiteto pessoa física não é parceiro cadastrado: os poucos casos que existem entram como "Outros", por serem irrelevantes na leitura.

**Outras origens** é a leitura consolidada dos canais, do jeito que a diretoria pede:

| grupo | o que entra |
|---|---|
| **Arquitetos** | todo orçamento trazido por um escritório de arquitetura parceiro |
| **Construtoras** | todo orçamento trazido por uma construtora parceira |
| **Indicação de clientes** | clientes indicados por outros clientes e clientes que voltam (reincidentes) |
| **Canais próprios** | WhatsApp, Instagram, Facebook, SAC/showroom e anúncios: o cliente procurou a empresa |
| **Outros** | parceiro não identificado ou irrelevante |

A visão **por parceiros** é o detalhe da mesma informação: qual escritório, qual construtora e qual cliente indicador trouxe cada orçamento. As duas visões vêm da mesma coluna do sistema, agrupada de dois jeitos; o pipeline garante que os totais batem por construção.

## 4. Vendedores, comissões e margem

Cada orçamento tem **um vendedor responsável** (e, quando há projeto 3D, um projetista). A comissão do vendedor é um percentual do valor líquido que **cai conforme o desconto concedido**: 1% sem desconto, 0,75% com desconto de até 10%, 0,5% acima disso. O parceiro recebe a reserva técnica (5% para escritórios, 3% para construtoras, negociável por parceiro). O projetista 3D recebe 0,25% sobre os itens que gerou. Comissões são apuradas por competência (o mês do ganho) e pagas depois do primeiro recebimento.

O valor **bruto** é a soma dos itens a preço de tabela; o **líquido** é o bruto menos o desconto negociado. A **margem líquida**, como a diretoria a chama, é a razão líquido ÷ bruto (quanto do preço de tabela sobreviveu à negociação). Como os itens carregam custo, o pipeline entrega também a margem sobre o custo, que a empresa nunca conseguiu ver.

## 5. A história nos números (2021 a setembro de 2026)

O universo sintético cobre **janeiro de 2021 a 4 de setembro de 2026, 18h** (a data corrente do universo) e conta uma história deliberada, para que os dashboards pareçam a realidade de uma empresa e permitam discutir decisões, e não gráficos sem sentido.

| ano | unidades | vendedores (fim do ano) | orçamentos (aprox.) | conversão | leitura |
|---|---|---|---|---|---|
| 2021 | 1 (Jardins) | 7 | 1.500 | crítica (~9%) | showroom novo, muita curiosidade pós-pandemia, equipe pequena, sem follow-up |
| 2022 | 1 | 8 | 1.750 | ruim (~13%) | processo comercial começa a existir; conversão melhora devagar |
| 2023 | 2 (abre Itaim em março) | 12 | 2.350 | regular (~18%) | segunda unidade, contratações, primeiros escritórios parceiros |
| 2024 | 2 | 15 | 2.750 | regular a boa (~24%) | **nova gestão comercial**: programa de parceiros (comissão, eventos), metas por vendedor, follow-up obrigatório |
| 2025 | 3 (abre Alto de Pinheiros em fevereiro) | 19 | 3.500 | boa (~31%) | terceira unidade; construtoras entram como parceiras |
| 2026 (até 04/09) | 3 | 22 | 2.700 (~4.000 no ano) | excelente (~40%) | maturidade comercial; a diretoria quer medir e premiar |

O crescimento de volume vem da expansão (novas unidades e novos vendedores), e não de saltos inexplicáveis: unidade a unidade, o crescimento é discreto e saudável (entre 10% e 15% ao ano). A conversão evolui em degraus explicáveis pela história. Vendedores entram por aumento de demanda e alguns saem ao longo do caminho, como em qualquer equipe.

**Sazonalidade.** O primeiro bimestre é fraco (férias, carnaval, orçamento da família comprometido); a demanda aquece a partir de março e abril; o auge vai de agosto a novembro, porque quem reforma quer a casa, a casa de praia ou o sítio prontos para as festas de fim de ano; dezembro cai em orçamentos novos, mas concentra fechamentos e instalações. Orçamentos nascem de segunda a sexta, com um pouco de sábado (showroom) e quase nada de domingo.

**Perfil de fechamento.** Orçamentos ganhos fecham rápido (mediana de duas semanas; um quarto em dois dias); perdidos demoram (mediana de dois meses e meio, muitos marcados como "sem retorno" meses depois). Cerca de um em cada seis clientes volta para um segundo orçamento.

## 6. As dores que motivaram o projeto

1. **Nenhum relatório confiável da área comercial.** A diretoria não consegue responder, com números que batem, quanto vendeu, quanto pagou de comissão, quantos orçamentos estão abertos, ganhos e perdidos, e como isso evolui. As reuniões executivas se apoiam em planilhas montadas à mão por cada gestor.
2. **O SLA de conversão existe no papel e não nos dados.** A empresa definiu faixas para a taxa de conversão e não tem estrutura para medi-las por vendedor, canal ou parceiro.
3. **A tentativa anterior de BI travava o sistema.** O relatório contratado lia direto do banco de produção; a cada atualização o sistema de vendas ficava quase inoperante. Foi desligado, e o medo de repetir o gasto e o problema é real.

## 7. Os indicadores que o pipeline precisa entregar

Todos em **volume** (quantidade) e em **dinheiro** (bruto e líquido), para qualquer recorte de vendedor, cliente, canal (outras origens) e parceiro, na visão semanal, mensal e anual:

| pergunta da diretoria | indicador | eixo de tempo |
|---|---|---|
| Quanto vendeu? | vendas (quantidade, bruto, líquido) | data do ganho |
| Quanto de comissões? | comissão de vendedor, de parceiro e de 3D | competência do ganho |
| Qual o maior valor vendido? Quem mais vendeu em volume? | maior venda; ranking por quantidade | data do ganho |
| Qual a margem líquida? | líquido ÷ bruto (e margem sobre custo) | data do ganho |
| Quantos orçamentos foram feitos? | orçamentos (quantidade, bruto, líquido) | data de cadastro |
| Quantos estão em aberto, perdidos, ganhos? | orçamentos por grupo de fase, com totais bruto e líquido | cadastro (situação atual) e **posição histórica** (quantos estavam abertos naquela data) |
| Qual a taxa de conversão e a de perda? | ganhos ÷ orçamentos, perdidos ÷ orçamentos | cadastro |
| Ticket médio, tempo até fechar, motivo da perda | complementos para a análise | ganho/perda |

**SLA da taxa de conversão**, definido pela empresa:

| faixa | taxa de conversão |
|---|---|
| Crítico | 0% a 10% |
| Ruim | acima de 10% até 15% |
| Regular | acima de 15% até 25% |
| Boa | acima de 25% até 40% |
| Excelente | acima de 40% |

Para a **taxa de perda** a leitura é invertida (quanto menor, melhor). As faixas vivem numa dimensão de bandas no modelo multidimensional, para que mudar o SLA seja editar linhas, e não código.

> **Observação registrada para a diretoria:** com a definição literal (perda = espelho da conversão), uma carteira com 41% de conversão e 45% de perda seria "excelente" num indicador e "crítica" no outro, porque os orçamentos em aberto ficam no meio. O pipeline entrega as duas taxas com a definição do cliente e deixa as bandas parametrizáveis; a calibração das faixas de perda é uma decisão de negócio a confirmar.

## 8. Os ritos executivos

A diretoria faz apresentações **mensais, trimestrais, semestrais e anuais**, sempre comparativas:

- **Mensal:** o mês corrente contra o mesmo mês dos dois anos anteriores (agosto de 2026 contra agosto de 2025 e agosto de 2024).
- **Semestral (em agosto):** janeiro a julho de cada um dos três anos.
- **Anual (primeiro dia útil de fevereiro):** os três anos fechados, lado a lado.

O que se decide nelas: comissões e premiação de vendedores, premiação de parceiros, investimento e reestruturação de áreas, eventos e premiação de clientes fiéis, e a leitura da saúde comercial da empresa. Por isso o modelo multidimensional nasce com calendário preparado para "mesmo período do ano anterior" e acumulados, e o histórico de fases preserva a posição de cada orçamento em qualquer data.

## 9. O que o projeto entrega

Um **staging** em SQL Server que espelha o banco do sistema comercial por **carga incremental diária** (a produção respira, a dor 3 acaba) e um pipeline analítico (bronze → silver → gold → star schema) que reconstrói todos os indicadores de **uma única fonte da verdade**: dimensões conformadas de tempo, vendedor, cliente, canal, parceiro e fase; fatos de orçamento, venda, comissão e posição do funil. No fim da esteira, um warehouse multidimensional em SQL Server (local ou em nuvem) alimenta dashboards web e Power BI, com os comparativos entre anos e as faixas de SLA por construção.

Fora do escopo deste caso, e deliberadamente: temperatura de orçamento e pontuação preditiva. A empresa ainda não mede isso, e um projeto de ciência de dados sobre esta mesma base fica para depois.

---

[Início](#topo)
