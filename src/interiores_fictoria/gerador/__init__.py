"""Gerador determinístico do sistema comercial da Fictoria (a "produção" simulada).

O universo inteiro (2021 até o fim de 2027) é PLANEJADO a partir de uma semente fixa:
cada orçamento nasce com sua linha do tempo completa (itens, fases, desfecho, follow-ups,
recebimentos, obra). O gerador então MATERIALIZA o banco "como ele estaria" numa data T
(a data corrente do universo, ou qualquer instante posterior) e sincroniza por MERGE.
Rodar de novo com a mesma T não muda nada; rodar com T maior aplica só o que aconteceu
entre as duas datas, que é exatamente o que uma produção real faria.
"""

from __future__ import annotations

from datetime import datetime

SEMENTE = 20260906
DATA_CORRENTE = datetime(2026, 9, 4, 18, 0, 0)
# Horizonte planejado: o universo tem futuro para o relógio poder avançar nas demos.
HORIZONTE = datetime(2027, 12, 31, 23, 59, 59)
