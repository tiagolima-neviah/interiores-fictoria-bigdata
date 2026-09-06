"""Parâmetros do universo Fictoria: a narrativa em números.

Tudo que a régua de validação cobra nasce daqui (volumes, arco de conversão, mix de
canal, sazonalidade, valores, prazos, sujeira). Mudar a história é mudar este arquivo.
As bandas da régua vivem em `validacao/bandas.py`, separadas de propósito: o gerador
não pode "corrigir" a régua, e a régua não lê o gerador.
"""

from __future__ import annotations

from datetime import date

# --- Volume de orçamentos (tipo Venda) por ano ----------------------------------
# 2026 e 2027 são anos inteiros planejados; a data corrente corta em 04/09/2026.
ORCAMENTOS_POR_ANO: dict[int, int] = {
    2021: 1_500,
    2022: 1_750,
    2023: 2_350,
    2024: 2_750,
    2025: 3_500,
    2026: 4_000,
    2027: 4_450,
}

# Sazonalidade: participação de cada mês no ano (soma 100).
SAZONALIDADE_MES: dict[int, float] = {
    1: 6.0,
    2: 6.5,
    3: 7.5,
    4: 8.5,
    5: 9.0,
    6: 8.5,
    7: 8.0,
    8: 9.0,
    9: 9.5,
    10: 10.5,
    11: 9.5,
    12: 7.5,
}
RUIDO_MENSAL = 0.10  # ±10% para a curva não parecer desenhada

# Dia da semana (0 = segunda): peso relativo de cadastro de orçamentos.
PESO_DIA_SEMANA: dict[int, float] = {0: 19, 1: 20, 2: 20, 3: 18, 4: 17.5, 5: 5, 6: 0.5}
HORA_INICIO, HORA_FIM = 9, 19

# Orçamentos que não são Venda (assistência, garantia, cortesia) existem e são filtrados
# pelo BI: proporção sobre o total gerado.
SHARE_NAO_VENDA = 0.06
# Cancelados (saem de todas as contas).
SHARE_CANCELADO = 0.015

# --- Conversão (sobre fechados) por ano: o arco crítico → excelente -------------
CONVERSAO_POR_ANO: dict[int, float] = {
    2021: 0.095,
    2022: 0.135,
    2023: 0.185,
    2024: 0.24,
    2025: 0.31,
    2026: 0.405,
    2027: 0.42,
}
# Fatores relativos de conversão (normalizados por ano contra o mix do ano).
FATOR_CONVERSAO_GRUPO: dict[str, float] = {
    "ARQUITETOS": 1.30,
    "CONSTRUTORAS": 1.30,
    "INDICACAO_CLIENTE": 1.15,
    "CANAL_PROPRIO": 0.85,
    "OUTROS": 0.80,
}
FATOR_CONVERSAO_CANAL: dict[str, float] = {"INSTAGRAM": 0.65, "FACEBOOK": 0.65, "ANUNCIO": 0.65}
SIGMA_FATOR_VENDEDOR = 0.25
FATOR_VALOR_ALTO, LIMITE_VALOR_ALTO = 0.70, 400_000.0
FATOR_VALOR_BAIXO, LIMITE_VALOR_BAIXO = 1.15, 20_000.0

# --- Mix de canal do orçamento por ano (soma 100) -------------------------------
# código do canal → participação. Os grupos vêm do catálogo `origem_contato`.
MIX_CANAL_POR_ANO: dict[int, dict[str, float]] = {
    2021: {
        "WHATSAPP": 34,
        "INSTAGRAM": 8,
        "FACEBOOK": 4,
        "SAC": 14,
        "ANUNCIO": 2,
        "IND_CLIENTE": 24,
        "ARQUITETO": 11,
        "CONSTRUTORA": 1,
        "OUTROS": 2,
    },
    2022: {
        "WHATSAPP": 32,
        "INSTAGRAM": 9,
        "FACEBOOK": 3,
        "SAC": 12,
        "ANUNCIO": 2,
        "IND_CLIENTE": 25,
        "ARQUITETO": 14,
        "CONSTRUTORA": 1,
        "OUTROS": 2,
    },
    2023: {
        "WHATSAPP": 29,
        "INSTAGRAM": 9,
        "FACEBOOK": 3,
        "SAC": 10,
        "ANUNCIO": 1,
        "IND_CLIENTE": 24,
        "ARQUITETO": 20,
        "CONSTRUTORA": 2,
        "OUTROS": 2,
    },
    2024: {
        "WHATSAPP": 25,
        "INSTAGRAM": 10,
        "FACEBOOK": 2,
        "SAC": 8,
        "ANUNCIO": 1,
        "IND_CLIENTE": 23,
        "ARQUITETO": 26,
        "CONSTRUTORA": 3,
        "OUTROS": 2,
    },
    2025: {
        "WHATSAPP": 23,
        "INSTAGRAM": 10,
        "FACEBOOK": 2,
        "SAC": 7,
        "ANUNCIO": 1,
        "IND_CLIENTE": 22,
        "ARQUITETO": 28,
        "CONSTRUTORA": 5,
        "OUTROS": 2,
    },
    2026: {
        "WHATSAPP": 22,
        "INSTAGRAM": 10,
        "FACEBOOK": 2,
        "SAC": 6,
        "ANUNCIO": 1,
        "IND_CLIENTE": 22,
        "ARQUITETO": 29,
        "CONSTRUTORA": 6,
        "OUTROS": 2,
    },
    2027: {
        "WHATSAPP": 21,
        "INSTAGRAM": 11,
        "FACEBOOK": 2,
        "SAC": 6,
        "ANUNCIO": 1,
        "IND_CLIENTE": 22,
        "ARQUITETO": 29,
        "CONSTRUTORA": 6,
        "OUTROS": 2,
    },
}
# Orçamentos de parceiro cujo parceiro não foi cadastrado (texto livre): vira OUTROS.
SHARE_PARCEIRO_SEM_CADASTRO = 0.05

# --- Unidades e equipe ----------------------------------------------------------
UNIDADES: list[tuple[int, str, str, str, date]] = [
    # id, sigla, nome, bairro, abertura
    (1, "JAR", "Fictoria Jardins", "Jardim Paulista", date(2021, 1, 4)),
    (2, "ITA", "Fictoria Itaim", "Itaim Bibi", date(2023, 3, 6)),
    (3, "APN", "Fictoria Alto de Pinheiros", "Alto de Pinheiros", date(2025, 2, 3)),
]
PESO_UNIDADE: dict[int, float] = {1: 1.0, 2: 0.85, 3: 0.75}

# Contratações e desligamentos de vendedores: (unidade, admissão, desligamento, perfil).
# Perfil de follow-up: D disciplinado, M mediano, R relapso. Fim de ano: 7, 8, 12, 15, 19, 22.
VENDEDORES: list[tuple[int, date, date | None, str]] = [
    (1, date(2021, 1, 4), None, "D"),
    (1, date(2021, 1, 4), None, "M"),
    (1, date(2021, 1, 4), date(2023, 10, 31), "R"),
    (1, date(2021, 1, 4), None, "M"),
    (1, date(2021, 1, 4), None, "R"),
    (1, date(2021, 1, 4), date(2022, 11, 30), "M"),
    (1, date(2021, 1, 4), None, "D"),
    (1, date(2022, 3, 1), None, "M"),
    (1, date(2022, 8, 1), None, "D"),
    (2, date(2023, 3, 6), None, "M"),
    (2, date(2023, 3, 6), None, "D"),
    (2, date(2023, 3, 6), date(2024, 9, 30), "R"),
    (1, date(2023, 6, 1), None, "M"),
    (2, date(2023, 9, 1), None, "M"),
    (1, date(2024, 2, 1), None, "D"),
    (1, date(2024, 5, 2), None, "M"),
    (2, date(2024, 3, 1), None, "M"),
    (2, date(2024, 8, 1), date(2025, 7, 31), "R"),
    (3, date(2025, 2, 3), None, "D"),
    (3, date(2025, 2, 3), None, "M"),
    (3, date(2025, 2, 3), None, "M"),
    (3, date(2025, 2, 3), None, "R"),
    (2, date(2025, 6, 2), None, "D"),
    (3, date(2026, 1, 12), None, "M"),
    (1, date(2026, 3, 2), None, "D"),
    (2, date(2026, 5, 4), None, "M"),
]
FOLLOWUP_MEDIA_POR_PERFIL: dict[str, float] = {"D": 6.0, "M": 3.0, "R": 0.3}

# --- Parceiros ------------------------------------------------------------------
N_ESCRITORIOS = 600
N_CONSTRUTORAS = 40
# Entrada de parceiros ao longo do tempo (participação do total por ano).
ENTRADA_PARCEIROS_POR_ANO: dict[int, float] = {
    2021: 0.10,
    2022: 0.12,
    2023: 0.20,
    2024: 0.30,
    2025: 0.18,
    2026: 0.08,
    2027: 0.02,
}
COMISSAO_PADRAO_ESCRITORIO = 5.0
COMISSAO_PADRAO_CONSTRUTORA = 3.0
ZIPF_PARCEIROS = 0.9  # cauda longa: top-10 ~15%, top-50 ~35%

# --- Clientes -------------------------------------------------------------------
SHARE_CLIENTE_RECORRENTE = 0.18
SHARE_CLIENTE_PJ = 0.08
SHARE_ENDERECO_LITORAL_CAMPO = 0.15

# --- Valores --------------------------------------------------------------------
TICKET_BRUTO_MEDIANA = 70_000.0
TICKET_BRUTO_SIGMA = 1.15
TICKET_BRUTO_MIN, TICKET_BRUTO_MAX = 2_000.0, 4_000_000.0
INFLACAO_ANUAL = 0.05
ITENS_MEDIANA, ITENS_SIGMA, ITENS_MIN, ITENS_MAX = 15.0, 0.5, 3, 60
SHARE_SEM_DESCONTO = 0.30
DESCONTO_MIN, DESCONTO_MAX = 6.0, 25.0
# Comissão do vendedor por faixa de desconto (limite superior do desconto → %).
COMISSAO_VENDEDOR_FAIXAS: list[tuple[float, float]] = [(0.0, 1.0), (10.0, 0.75), (100.0, 0.5)]
COMISSAO_3D = 0.25
SHARE_COM_PROJETISTA_3D = 0.55
SHARE_COM_SUPERVISOR = 0.50
COMISSAO_SUPERVISOR = 0.10

# --- Prazos (dias) --------------------------------------------------------------
DIAS_FECHAR_GANHO_MEDIANA, DIAS_FECHAR_GANHO_SIGMA = 13.0, 1.25
DIAS_FECHAR_PERDIDO_MEDIANA, DIAS_FECHAR_PERDIDO_SIGMA = 75.0, 0.95
DIAS_FECHAR_MAX = 420
# Etapas de execução (após o ganho): nome, prazo padrão em dias, probabilidade de ocorrer.
ETAPAS_EXECUCAO: list[tuple[str, int, float]] = [
    ("AGENDAMENTO MEDIÇÃO", 2, 1.0),
    ("MEDIÇÃO", 3, 1.0),
    ("PROJETO/PRODUÇÃO", 10, 1.0),
    ("COTAÇÃO", 5, 0.9),
    ("VIABILIDADE", 3, 0.6),
    ("DEFINIÇÃO FATURAMENTO", 2, 1.0),
    ("LIBERAÇÃO DE OBRA", 3, 1.0),
    ("ENTREGA FORNECEDOR", 25, 1.0),
    ("PRÉ PROGRAMAÇÃO", 3, 0.8),
    ("PLANEJAMENTO INSTALAÇÃO", 5, 1.0),
    ("INSTALAÇÃO", 7, 1.0),
    ("CORREÇÃO", 5, 0.25),
    ("APROVAÇÃO PÓS VENDA", 5, 0.9),
    ("FINALIZADO", 0, 1.0),
]
SHARE_ETAPA_ATRASADA = 0.30
SHARE_GANHO_ANTIGO_SEM_ETAPAS = 0.15  # ganhos de 2021-2022 sem trilha de execução

# Recebimento
PARCELAS_OPCOES: list[tuple[int, float]] = [(1, 0.15), (3, 0.25), (6, 0.30), (10, 0.20), (12, 0.10)]
ENTRADA_PCT = 30.0
SHARE_PAGAMENTO_ATRASADO, ATRASO_DIAS_MAX = 0.10, 60
SHARE_PARCELA_NUNCA_PAGA = 0.03
DIAS_PAGAMENTO_COMISSAO = 30

# Obra
SHARE_MEDICAO = 0.60
SHARE_REMEDICAO_GANHO = 0.10
INSTALACAO_LEAD_MIN, INSTALACAO_LEAD_MAX = 45, 90
INSTALACAO_DURACAO_MIN, INSTALACAO_DURACAO_MAX = 3, 20
SHARE_INSTALACAO_PROBLEMA = 0.15

# Trilhas
HISTORICO_MEDIA = 6.0
AUDITORIA_CAMPOS_CRIACAO = 20
REVISOES_MEDIA = 1.2

# --- Catálogo de sujeira (taxas-alvo) -------------------------------------------
SUJEIRA_DATA_SENTINELA = 0.02  # dt_finalizou = 1900-01-01 em vez de nulo
SUJEIRA_FECHOU_ANTES_CADASTRO = 0.003
SUJEIRA_VALOR_ZERO = 0.015
SUJEIRA_CLIENTE_GRAFIA = 0.03
SUJEIRA_CEP_AUSENTE = 0.08
SUJEIRA_BAIRRO_AUSENTE = 0.05
SUJEIRA_ITEM_CANCELADO_SOMADO = 0.005  # só 2021-2022
SUJEIRA_COMISSAO_DIVERGENTE = 0.01
