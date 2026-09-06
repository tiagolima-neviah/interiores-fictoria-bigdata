"""Bandas de aceite da origem sintética: o contrato que o gerador deve honrar.

Cada banda é (mínimo, máximo) inclusivo. Elas derivam do plano de sintetização aprovado
(volumes, arco de conversão, mix de canal, sazonalidade, valores, prazos, sujeira) e são
propositalmente independentes de `gerador/parametros.py`: o gerador não lê a régua e a
régua não lê o gerador. Fora da banda, a base é REGENERADA, não contornada.
"""

from __future__ import annotations

Banda = tuple[float, float]

# --- Volumes (orçamentos de venda, não cancelados, por ano de cadastro) ----------
# 2026 vai só até a data corrente do universo (04/09/2026).
ORCAMENTOS_POR_ANO: dict[int, Banda] = {
    2021: (1_380, 1_620),
    2022: (1_610, 1_890),
    2023: (2_160, 2_540),
    2024: (2_530, 2_970),
    2025: (3_220, 3_780),
    2026: (2_350, 2_800),
}
TOTAL_ORCAMENTO_ITEM: Banda = (150_000, 450_000)
TOTAL_AUDITORIA: Banda = (250_000, 900_000)

# --- O arco da história: conversão sobre fechados ----------------------------------
# Anos fechados: orçamentos com ≥ 180 dias de maturidade. 2026 é o ano corrente: como os
# ganhos fecham rápido e os perdidos demoram, a leitura sobre fechados fica inflada de
# propósito (é o que um dashboard real mostra em setembro), daí a banda mais larga e mais alta.
CONVERSAO_POR_ANO: dict[int, Banda] = {
    2021: (0.075, 0.115),
    2022: (0.115, 0.155),
    2023: (0.165, 0.205),
    2024: (0.215, 0.265),
    2025: (0.285, 0.345),
    2026: (0.40, 0.58),
}
# Carteira aberta no ano corrente (fase ABERTO / orçamentos de 2026).
SHARE_ABERTO_2026: Banda = (0.10, 0.36)

# --- Equipe: vendedores com pelo menos um orçamento no ano (inclui quem saiu no ano) ----
VENDEDORES_POR_ANO: dict[int, Banda] = {
    2021: (7, 7),
    2022: (8, 9),
    2023: (12, 13),
    2024: (15, 16),
    2025: (19, 20),
    2026: (21, 22),
}

# --- Canais e parceiros ------------------------------------------------------------
SHARE_ARQUITETOS_2021: Banda = (0.06, 0.14)
SHARE_ARQUITETOS_2026: Banda = (0.23, 0.33)
SHARE_CANAL_PROPRIO_2021: Banda = (0.54, 0.69)
SHARE_CANAL_PROPRIO_2026: Banda = (0.34, 0.48)
SHARE_COM_PARCEIRO_2026: Banda = (0.27, 0.39)

# --- Sazonalidade: (ago+set+out+nov) / (jan+fev), anos fechados 2021-2025 ------------
RAZAO_SAZONAL: Banda = (2.4, 3.8)

# --- Valores -------------------------------------------------------------------------
TICKET_BRUTO_MEDIANA: Banda = (55_000, 110_000)
TICKET_BRUTO_P90: Banda = (300_000, 650_000)
VENDA_LIQUIDA_MEDIANA: Banda = (22_000, 80_000)
DESCONTO_MEDIO_VENDAS: Banda = (0.07, 0.16)
COMISSAO_VENDEDOR_SOBRE_LIQUIDO: Banda = (0.005, 0.011)

# --- Prazos (dias, mediana) ------------------------------------------------------------
DIAS_FECHAR_GANHO: Banda = (7, 22)
DIAS_FECHAR_PERDIDO: Banda = (50, 110)

# --- Clientes ------------------------------------------------------------------------
SHARE_CLIENTES_RECORRENTES: Banda = (0.08, 0.25)

# --- Catálogo de sujeira (taxas-alvo, propositais) -----------------------------------
SUJEIRA_DATA_SENTINELA: Banda = (0.010, 0.035)  # dt_finalizou = 1900-01-01 entre os fechados
SUJEIRA_FECHOU_ANTES_CADASTRO: Banda = (0.0005, 0.008)
SUJEIRA_VALOR_ZERO: Banda = (0.005, 0.030)
SHARE_SEM_FOLLOW_UP: Banda = (0.15, 0.55)
SHARE_GANHO_SEM_ETAPAS: Banda = (0.02, 0.20)

# --- Integridade de negócio (o que FK não garante) ----------------------------------
DIVERGENCIA_SOMA_ITENS: Banda = (0.0, 0.012)  # bruto ≠ soma dos itens não cancelados
ORCAMENTO_SEM_ITEM: Banda = (0.0, 0.001)
GANHO_SEM_RECEBIMENTO: Banda = (0.0, 0.03)
GANHO_SEM_COMISSAO: Banda = (0.0, 0.03)
FASE_ATUAL_COERENTE_COM_TRILHA: Banda = (0.999, 1.0)
FECHAMENTO_COERENTE_COM_FASE: Banda = (0.96, 1.0)
