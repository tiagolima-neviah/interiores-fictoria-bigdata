<a id="topo"></a>

# Régua de Validação: o contrato de aceite dos dados sintéticos

<!-- nav:start -->
[Home](../README.md) | [← Modelo de Dados](03_modelo_dados_staging.md) | [Guia de Reprodução →](05_guia_reproducao.md)
<!-- nav:end -->

> Antes de qualquer camada analítica consumir o sistema comercial simulado, os dados sintéticos passam por uma régua de validação versionada: 46 verificações com bandas de aceite (mínimo e máximo) para volumes, o arco de conversão, a equipe, os canais, a sazonalidade, valores, prazos, sujeira e integridade de negócio. A regra é inegociável: **banda estourada não se contorna, regenera-se a base**.

## 1. Por que uma régua

Dado sintético sem contrato de aceite é dado inventado duas vezes: uma no gerador, outra na cabeça de quem analisa. A régua fecha esse buraco: ela declara, antes de o gerador rodar em escala, o que a base precisa exibir para ser aceita (quantos orçamentos por ano, qual conversão em cada ano, quantos vendedores, que mistura de canais, que ticket, que taxa de sujeira). O gerador não lê a régua e a régua não lê os parâmetros do gerador; os dois derivam do mesmo plano de negócio, mas por caminhos independentes, e é essa independência que dá valor ao veredito.

## 2. O que a régua verifica (46 checks na v1)

- **Volumes:** orçamentos de venda por ano (2021 a 2026, o último até a data corrente do universo) e o total das duas maiores tabelas (itens e auditoria).
- **O arco da história:** conversão sobre fechados por ano, seguindo a narrativa crítico → excelente. Anos fechados usam orçamentos com pelo menos 180 dias de maturidade; 2026 é lido como um dashboard real leria em setembro: como os ganhos fecham rápido e os perdidos demoram, a leitura sobre fechados do ano corrente fica inflada de propósito, e a banda é mais larga e mais alta. A carteira aberta de 2026 também tem banda.
- **Equipe:** vendedores com pelo menos um orçamento em cada ano (7 em 2021, 22 em 2026, contando quem saiu no meio do ano).
- **Canais e parceiros:** participação dos grupos Arquitetos e Canal próprio em 2021 e 2026 (o programa de parceiros muda o mix) e a fatia de orçamentos com parceiro cadastrado.
- **Sazonalidade:** a razão entre o auge (agosto a novembro) e o primeiro bimestre nos anos fechados.
- **Valores e prazos:** mediana e p90 do ticket bruto, mediana da venda líquida, desconto médio nas vendas, comissão do vendedor sobre o líquido, mediana de dias até fechar (ganhos e perdidos, pela trilha de fases).
- **Clientes:** fatia de clientes recorrentes.
- **Catálogo de sujeira:** taxas de defeito proposital dentro das faixas planejadas (data-sentinela no fechamento, fechamento anterior ao cadastro, orçamento de valor zero, orçamentos sem follow-up, ganhos antigos sem trilha de execução).
- **Integridade de negócio (o que FK não garante):** bruto igual à soma dos itens não cancelados, orçamento sem item, ganho sem recebimento, ganho sem comissão apurada, fase atual igual à última fase da trilha, fechamento coerente com a fase.

## 3. Como rodar

Com o SQL Server de pé e a origem populada (ver [Guia de Reprodução](05_guia_reproducao.md)):

```bash
uv run regua-origem            # valida o sistema comercial simulado (db_fictoria)
uv run regua-origem --staging  # valida o espelho (stg_fictoria) com os mesmos checks
```

A saída lista cada check com o valor observado, a banda e o veredito, e o processo termina com código de saída 1 se qualquer check reprovar (pronto para CI). Contra um banco vazio, a régua reprova tudo: ela existe justamente para só liberar a base populada e coerente. Rodar a mesma régua contra o staging prova que o espelho é fiel: os 46 valores observados têm de ser idênticos aos da origem.

## 4. Onde vivem as bandas

Em [`src/interiores_fictoria/validacao/bandas.py`](../src/interiores_fictoria/validacao/bandas.py), com um comentário por grupo explicando a intenção. As bandas da v1 são deliberadamente largas; a calibração fina acontece nas primeiras rodadas do gerador e cada estreitamento é um commit revisado. O resultado da primeira rodada aprovada está registrado no [Guia de Reprodução](05_guia_reproducao.md).

---

[Início](#topo)
