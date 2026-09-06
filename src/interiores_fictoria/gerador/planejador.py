"""Planejamento do universo: cada orçamento nasce com a linha do tempo inteira.

Determinístico: a mesma semente produz exatamente os mesmos planos. A conversão de
cada ano é calibrada em duas passagens (cabeçalho → normalização do fator → desfecho),
para o arco crítico → excelente ser cobrado pela régua com precisão.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from interiores_fictoria.gerador import HORIZONTE, SEMENTE, nomes
from interiores_fictoria.gerador import parametros as P
from interiores_fictoria.gerador.mundo import (
    AMBIENTES,
    CATEGORIAS,
    CONDICAO_POR_PARCELAS,
    FASE_GANHO,
    FASE_PERDIDO,
    FORMAS_PAGAMENTO,
    MOTIVOS_PERDA,
    ORIGEM_GRUPO,
    ORIGEM_ID,
    ItemCatalogo,
    Mundo,
    Usuario,
)

UM_DIA = timedelta(days=1)
SENTINELA = datetime(1900, 1, 1)


@dataclass
class Endereco:
    tipo: str
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cidade: str
    uf: str
    cep: str | None
    principal: bool


@dataclass
class Cliente:
    id: int
    tipo_pessoa: str
    nome: str
    nome_fantasia: str | None
    cpf_cnpj: str | None
    email: str | None
    telefone: str | None
    dt_nascimento: date | None
    origem_id: int | None
    cliente_indicador_id: int | None
    parceiro_indicador_id: int | None
    unidade_id: int
    dt_cadastro: datetime
    nm_cadastro: str
    enderecos: list[Endereco] = field(default_factory=list)


@dataclass
class Item:
    ambiente_id: int
    item_id: int
    descricao: str
    qtd: float
    vl_unitario: float
    vl_custo: float
    vl_markup: float
    vl_total: float
    ordem: int
    dt_cancelou: datetime | None
    gera_comissao: bool


@dataclass
class Fase:
    fase_id: int
    dt_entrada: datetime
    dt_saida: datetime | None


@dataclass
class Etapa:
    status_id: int
    dt_cadastro: datetime
    dt_limite: date
    dt_concluiu: datetime | None
    manual: bool


@dataclass
class FollowUp:
    dt_lanc: datetime
    usuario_id: int
    tipo: str
    obs: str
    proximo: date | None


@dataclass
class Historico:
    ds_acao: str
    dt_acao: datetime
    nm_acao: str
    fl_log: bool


@dataclass
class Auditoria:
    ds_campo: str
    vl_antigo: str | None
    vl_novo: str | None
    nm_alterou: str
    dt_alterou: datetime


@dataclass
class Parcela:
    nr: int
    dt_vencimento: date
    valor: float
    dt_pagamento: date | None
    vl_juros: float
    forma_id: int
    nr_documento: str


@dataclass
class Recebimento:
    dt_emissao: date
    vl_total: float
    nr_parcelas: int
    forma_id: int
    condicao_id: int
    parcelas: list[Parcela]


@dataclass
class Comissao:
    tipo: str
    usuario_id: int | None
    parceiro_id: int | None
    p: float
    vl_base: float
    vl: float
    competencia: str
    dt_apuracao: date
    dt_pagamento: date | None


@dataclass
class Medicao:
    medidor_id: int | None
    dt_agendada: datetime
    dt_realizada: datetime | None
    remedicao: bool
    obs: str | None


@dataclass
class EventoInstalacao:
    ds_acao: str
    dt_acao: datetime
    nm_acao: str
    item_ordem: int | None


@dataclass
class Instalacao:
    instalador_id: int | None
    dt_criacao: datetime
    dt_prevista: date
    dt_inicio: date | None
    dt_fim: date | None
    problema: bool
    ds_problema: str | None
    aprovado: bool | None
    dt_aprovacao: date | None
    eventos: list[EventoInstalacao]


@dataclass
class Orcamento:
    id: int
    nr: int
    unidade_id: int
    cliente: Cliente
    endereco_obra_idx: int | None
    tipo_id: int
    canal: str
    origem_id: int | None
    parceiro_id: int | None
    parceiro_texto: str | None
    vendedor: Usuario
    projetista_id: int | None
    supervisor_id: int | None
    dt_cadastro: datetime
    ds_objetivo: str
    itens: list[Item]
    vl_bruto: float
    vl_desconto: float
    porc_desconto: float
    vl_liquido: float
    p_com_vend: float | None
    p_com_parc: float | None
    p_com_3d: float | None
    forma_id: int | None
    condicao_id: int | None
    dt_prazo_entrega: date | None
    especial: bool
    garantia: bool
    dt_cancelou: datetime | None
    desfecho: str | None  # GANHO | PERDIDO | None (aberto no horizonte, ou cancelado)
    dt_fechamento: datetime | None
    dt_finalizou_registrado: datetime | None  # o que a tela grava (pode ser sentinela ou errado)
    motivo_perda_id: int | None
    fases: list[Fase]
    etapas: list[Etapa]
    follow_ups: list[FollowUp]
    historico: list[Historico]
    auditoria: list[Auditoria]
    recebimento: Recebimento | None
    comissoes: list[Comissao]
    medicoes: list[Medicao]
    instalacao: Instalacao | None
    # calibração
    fator_conversao: float = 1.0
    u_desfecho: float = 0.5


@dataclass
class Universo:
    mundo: Mundo
    clientes: list[Cliente]
    orcamentos: list[Orcamento]


# --- utilidades -----------------------------------------------------------------


def _poisson(rng: random.Random, media: float) -> int:
    if media <= 0:
        return 0
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def _lognormal(rng: random.Random, mediana: float, sigma: float) -> float:
    return mediana * math.exp(rng.gauss(0.0, sigma))


def _fmt_moeda(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _competencia(d: datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _escolher(rng: random.Random, pesos: Mapping[str, float]) -> str:
    chaves = list(pesos)
    return rng.choices(chaves, weights=[pesos[c] for c in chaves], k=1)[0]


# --- calendário de cadastros ----------------------------------------------------


def _datas_cadastro(ano: int, mes: int) -> list[datetime]:
    rng = random.Random(f"{SEMENTE}-mes-{ano}-{mes}")
    volume = P.ORCAMENTOS_POR_ANO[ano] / (1 - P.SHARE_NAO_VENDA)  # inclui os não-venda
    n = round(
        volume * P.SAZONALIDADE_MES[mes] / 100 * (1 + rng.uniform(-P.RUIDO_MENSAL, P.RUIDO_MENSAL))
    )
    primeiro = date(ano, mes, 1)
    dias = []
    d = primeiro
    abertura = P.UNIDADES[0][4]  # a empresa nasce com a primeira unidade
    while d.month == mes:
        if d >= abertura:
            dias.append(d)
        d += UM_DIA
    if not dias:
        return []
    pesos = [P.PESO_DIA_SEMANA[d.weekday()] for d in dias]
    saida = []
    for _ in range(n):
        d = rng.choices(dias, weights=pesos, k=1)[0]
        hora = rng.randint(P.HORA_INICIO, P.HORA_FIM - 1)
        saida.append(datetime(d.year, d.month, d.day, hora, rng.randint(0, 59), rng.randint(0, 59)))
    return sorted(saida)


# --- planejamento de um orçamento (passo 1: cabeçalho) --------------------------


@dataclass
class Cabecalho:
    nr: int
    dt: datetime
    unidade_id: int
    canal: str
    vendedor: Usuario
    tipo_id: int
    vl_bruto_alvo: float
    fator: float
    u_desfecho: float


def _unidade_para(rng: random.Random, dia: date) -> int:
    abertas = [
        (uid, P.PESO_UNIDADE[uid]) for uid, _, _, _, abertura in P.UNIDADES if abertura <= dia
    ]
    return rng.choices([u for u, _ in abertas], weights=[p for _, p in abertas], k=1)[0]


def _cabecalho(mundo: Mundo, nr: int, dt: datetime) -> Cabecalho:
    rng = random.Random(f"{SEMENTE}-orc-{nr}-a")
    unidade_id = _unidade_para(rng, dt.date())
    ativos = mundo.vendedores_ativos(unidade_id, dt.date()) or [
        v for v in mundo.vendedores() if v.dt_admissao <= dt.date()
    ]
    vendedor = rng.choices(ativos, weights=[v.forca for v in ativos], k=1)[0]
    canal = _escolher(rng, P.MIX_CANAL_POR_ANO[dt.year])
    tipo_id = 1 if rng.random() >= P.SHARE_NAO_VENDA else rng.choice([2, 2, 3, 4])
    inflacao = (1 + P.INFLACAO_ANUAL) ** (dt.year - 2021)
    bruto = _lognormal(rng, P.TICKET_BRUTO_MEDIANA * inflacao, P.TICKET_BRUTO_SIGMA)
    bruto = max(P.TICKET_BRUTO_MIN, min(P.TICKET_BRUTO_MAX, bruto))
    fator = P.FATOR_CONVERSAO_GRUPO[ORIGEM_GRUPO[canal]] * P.FATOR_CONVERSAO_CANAL.get(canal, 1.0)
    fator *= math.exp(
        math.log(vendedor.forca) * P.SIGMA_FATOR_VENDEDOR
    )  # vendedor forte converte mais
    if bruto > P.LIMITE_VALOR_ALTO:
        fator *= P.FATOR_VALOR_ALTO
    elif bruto < P.LIMITE_VALOR_BAIXO:
        fator *= P.FATOR_VALOR_BAIXO
    return Cabecalho(nr, dt, unidade_id, canal, vendedor, tipo_id, bruto, fator, rng.random())


# --- planejamento de um orçamento (passo 2: detalhe) ----------------------------


class Planejador:
    def __init__(self, mundo: Mundo) -> None:
        self.mundo = mundo
        self.clientes: list[Cliente] = []
        self.orcamentos: list[Orcamento] = []
        self._itens_por_categoria: dict[int, list[ItemCatalogo]] = {}
        for it in mundo.itens:
            self._itens_por_categoria.setdefault(it.categoria_id, []).append(it)
        self._peso_categoria = {c[0]: c[3] for c in CATEGORIAS}
        self._cv_categoria = {c[0]: (c[4], c[5]) for c in CATEGORIAS}

    # ----- clientes -----

    def _novo_cliente(self, rng: random.Random, cab: Cabecalho, parceiro_id: int | None) -> Cliente:
        pj = rng.random() < P.SHARE_CLIENTE_PJ
        ramos = ["Participações", "Consultoria", "Empreendimentos", "Comércio"]
        nome = (
            f"{rng.choice(nomes.SOBRENOMES)} {rng.choice(ramos)} Ltda"
            if pj
            else nomes.nome_pessoa(rng)
        )
        if rng.random() < P.SUJEIRA_CLIENTE_GRAFIA and self.clientes:
            nome = nomes.variar_grafia(rng.choice(self.clientes).nome, rng)
        dt_cadastro = cab.dt - timedelta(hours=rng.randint(0, 72))
        indicador = None
        if cab.canal == "IND_CLIENTE":
            anteriores = [c for c in self.clientes if c.dt_cadastro < dt_cadastro]
            if anteriores:
                indicador = rng.choice(anteriores).id
        cliente = Cliente(
            id=len(self.clientes) + 1,
            tipo_pessoa="PJ" if pj else "PF",
            nome=nome,
            nome_fantasia=nome.replace(" Ltda", "") if pj else None,
            cpf_cnpj=(nomes.cnpj(rng) if pj else nomes.cpf(rng)) if rng.random() < 0.93 else None,
            email=nomes.email(nome, rng) if rng.random() < 0.9 else None,
            telefone=nomes.telefone(rng),
            dt_nascimento=None
            if pj
            else date(rng.randint(1950, 1995), rng.randint(1, 12), rng.randint(1, 28)),
            origem_id=ORIGEM_ID[cab.canal],
            cliente_indicador_id=indicador,
            parceiro_indicador_id=parceiro_id,
            unidade_id=cab.unidade_id,
            dt_cadastro=dt_cadastro,
            nm_cadastro=cab.vendedor.login,
        )
        # endereços: residência (principal) e, às vezes, a obra em outro lugar (litoral/campo)
        bairro = nomes.bairro_sp(rng)
        cliente.enderecos.append(
            Endereco(
                "COMERCIAL" if pj else "RESIDENCIA",
                rng.choice(nomes.LOGRADOUROS),
                str(rng.randint(10, 2500)),
                f"apto {rng.randint(1, 30)}" if rng.random() < 0.45 else None,
                None if rng.random() < P.SUJEIRA_BAIRRO_AUSENTE else bairro,
                "São Paulo",
                "SP",
                None if rng.random() < P.SUJEIRA_CEP_AUSENTE else nomes.cep(rng),
                True,
            )
        )
        if rng.random() < P.SHARE_ENDERECO_LITORAL_CAMPO:
            cidade, uf, tipo = rng.choice(nomes.LITORAL_CAMPO)
            cliente.enderecos.append(
                Endereco(
                    tipo,
                    rng.choice(nomes.LOGRADOUROS),
                    str(rng.randint(1, 900)),
                    None,
                    rng.choice(["Centro", "Condomínio Reserva", "Praia", "Serra", None]),
                    cidade,
                    uf,
                    None if rng.random() < P.SUJEIRA_CEP_AUSENTE else nomes.cep(rng),
                    False,
                )
            )
        self.clientes.append(cliente)
        return cliente

    # ----- itens e valores -----

    def _itens(self, rng: random.Random, cab: Cabecalho, ano: int) -> list[Item]:
        n = int(round(_lognormal(rng, P.ITENS_MEDIANA, P.ITENS_SIGMA)))
        n = max(P.ITENS_MIN, min(P.ITENS_MAX, n))
        ambientes = rng.sample(range(1, len(AMBIENTES) + 1), k=rng.randint(1, 5))
        pesos_gamma = [rng.gammavariate(1.0, 1.0) for _ in range(n)]
        soma = sum(pesos_gamma)
        inflacao = (1 + P.INFLACAO_ANUAL) ** (ano - 2021)
        cats = list(self._peso_categoria)
        itens: list[Item] = []
        valor_zero = rng.random() < P.SUJEIRA_VALOR_ZERO
        for ordem, peso in enumerate(pesos_gamma, start=1):
            cat = rng.choices(cats, weights=[self._peso_categoria[c] for c in cats], k=1)[0]
            alvo = cab.vl_bruto_alvo * peso / soma
            disponiveis = [m for m in self._itens_por_categoria[cat] if m.dt_cadastro <= cab.dt]
            disponiveis = disponiveis or self._itens_por_categoria[cat]
            # o item precisa caber no valor-alvo da linha (closet não entra em orçamento pequeno)
            cabem = [m for m in disponiveis if m.vl_referencia * inflacao <= alvo * 1.5]
            mais_barato = min(disponiveis, key=lambda m: m.vl_referencia)
            modelo = rng.choice(cabem) if cabem else mais_barato
            unit = round(modelo.vl_referencia * inflacao * rng.uniform(0.95, 1.05), 2)
            if valor_zero:
                unit = 0.0
            if modelo.unidade_medida in ("UN", "VB") or modelo.unidade_medida == "H":
                qtd = max(1.0, float(round(alvo / max(unit, 1.0))))
            else:
                qtd = max(0.5, round(alvo / max(unit, 1.0), 2))
            total = round(qtd * unit, 2)
            custo = round(modelo.vl_custo_referencia * inflacao * rng.uniform(0.95, 1.05) * qtd, 2)
            markup = round(unit / max(modelo.vl_custo_referencia * inflacao, 1.0), 2)
            itens.append(
                Item(
                    rng.choice(ambientes),
                    modelo.id,
                    modelo.descricao,
                    qtd,
                    unit,
                    custo,
                    markup,
                    total,
                    ordem,
                    None,
                    modelo.fl_gera_comissao,
                )
            )
        return itens

    # ----- trilhas -----

    def _fases(
        self,
        rng: random.Random,
        dt: datetime,
        fechamento: datetime | None,
        desfecho: str | None,
        cancelou: datetime | None,
    ) -> list[Fase]:
        abertas = []
        if rng.random() < 0.35:
            abertas.append(1)
        if rng.random() < 0.55:
            abertas.append(2)
        abertas.append(3)
        if rng.random() < 0.85:
            abertas.append(4)
        if rng.random() < (0.75 if desfecho == "GANHO" else 0.45):
            abertas.append(5)
        fim = fechamento or cancelou or (dt + timedelta(days=P.DIAS_FECHAR_MAX))
        total = max((fim - dt).total_seconds(), 3600.0)
        pesos = [rng.gammavariate(1.5, 1.0) for _ in abertas]
        soma = sum(pesos)
        fases: list[Fase] = []
        cursor = dt
        for fase_id, peso in zip(abertas, pesos, strict=True):
            saida = cursor + timedelta(seconds=total * peso / soma)
            fases.append(Fase(fase_id, cursor, saida))
            cursor = saida
        if cancelou is not None:
            # a fase vigente no cancelamento fica aberta; as seguintes não acontecem
            recorte = [f for f in fases if f.dt_entrada < cancelou]
            if recorte:
                recorte[-1].dt_saida = None
            return recorte
        if desfecho is None:
            fases[-1].dt_saida = None  # aberto até o fim do horizonte
            return fases
        fases[-1].dt_saida = fim
        fases.append(Fase(FASE_GANHO if desfecho == "GANHO" else FASE_PERDIDO, fim, None))
        return fases

    def _etapas(self, rng: random.Random, ganho: datetime, ano: int) -> list[Etapa]:
        if ano <= 2022 and rng.random() < P.SHARE_GANHO_ANTIGO_SEM_ETAPAS:
            return []
        if ano >= 2023 and rng.random() < 0.05:
            return []
        etapas: list[Etapa] = []
        inicio = ganho + timedelta(days=1, hours=rng.randint(0, 8))
        for status_id, (_nome, prazo, prob) in enumerate(P.ETAPAS_EXECUCAO, start=1):
            if rng.random() > prob:
                continue
            limite = (inicio + timedelta(days=prazo)).date()
            dur = prazo * math.exp(rng.gauss(0.0, 0.35))
            if rng.random() < P.SHARE_ETAPA_ATRASADA:
                dur *= rng.uniform(1.1, 1.8)
            concluiu = inicio + timedelta(days=max(dur, 0.1))
            etapas.append(Etapa(status_id, inicio, limite, concluiu, rng.random() < 0.15))
            inicio = concluiu + timedelta(days=rng.uniform(0, 2))
        return etapas

    def _follow_ups(
        self, rng: random.Random, orc_dt: datetime, fim: datetime, vendedor: Usuario
    ) -> list[FollowUp]:
        n = _poisson(rng, P.FOLLOWUP_MEDIA_POR_PERFIL[vendedor.perfil])
        janela = max((min(fim, orc_dt + timedelta(days=180)) - orc_dt).total_seconds(), 3600.0)
        tipos = {
            "WHATSAPP": 45,
            "LIGACAO": 25,
            "EMAIL": 10,
            "VISITA": 8,
            "SHOWROOM": 7,
            "REUNIAO": 5,
        }
        obs = [
            "Cliente pediu revisão da proposta.",
            "Aguardando retorno do arquiteto.",
            "Visita ao showroom agendada.",
            "Enviado 3D atualizado.",
            "Cliente viaja, retomar semana que vem.",
            "Negociando condição de pagamento.",
            "Solicitou troca de acabamento da bancada.",
            "Sem retorno após dois contatos.",
            "Medição confirmada.",
            "Cliente comparando com concorrente.",
        ]
        saida = []
        for _ in range(n):
            lanc = orc_dt + timedelta(seconds=rng.uniform(3600, janela))
            saida.append(
                FollowUp(
                    lanc,
                    vendedor.id,
                    _escolher(rng, tipos),
                    rng.choice(obs),
                    (lanc + timedelta(days=rng.randint(2, 10))).date()
                    if rng.random() < 0.8
                    else None,
                )
            )
        return sorted(saida, key=lambda f: f.dt_lanc)

    def _historico_e_auditoria(
        self, rng: random.Random, orc: Orcamento
    ) -> tuple[list[Historico], list[Auditoria]]:
        quem = orc.vendedor.login
        hist = [Historico("Orçamento criado", orc.dt_cadastro, quem, True)]
        aud: list[Auditoria] = []
        campos = [
            "cod_cliente",
            "id_orcamento_tipo",
            "cod_user_vendedor",
            "ds_objetivo",
            "vl_total_bruto",
            "vl_desconto",
            "vl_total_liquido",
            "p_comissao",
            "id_forma_pagamento",
            "dt_prazo_entrega",
            "fl_pedido_especial",
            "fl_garantia",
            "cod_fornecedor_arquiteto",
            "id_endereco_entrega",
            "id_orcamento_fase",
            "nm_cadastrou",
            "id_condicao_parcelamento",
            "ds_esboco",
            "ds_cronograma",
            "cod_user_desenhista3D",
        ]
        for campo in campos[: P.AUDITORIA_CAMPOS_CRIACAO]:
            aud.append(Auditoria(campo, None, "(criação)", quem, orc.dt_cadastro))
        for anterior, seguinte in zip(orc.fases, orc.fases[1:], strict=False):
            hist.append(
                Historico(f"Fase alterada para {seguinte.fase_id}", seguinte.dt_entrada, quem, True)
            )
            aud.append(
                Auditoria(
                    "id_orcamento_fase",
                    str(anterior.fase_id),
                    str(seguinte.fase_id),
                    quem,
                    seguinte.dt_entrada,
                )
            )
            if seguinte.fase_id == 4:
                hist.append(
                    Historico(
                        "Proposta enviada ao cliente (v1)",
                        seguinte.dt_entrada + timedelta(hours=2),
                        quem,
                        False,
                    )
                )
        fim = orc.dt_fechamento or orc.dt_cancelou or (orc.dt_cadastro + timedelta(days=120))
        janela = max((fim - orc.dt_cadastro).total_seconds(), 7200.0)
        liquido = orc.vl_bruto
        for k in range(_poisson(rng, P.REVISOES_MEDIA)):
            quando = orc.dt_cadastro + timedelta(seconds=rng.uniform(3600, janela))
            novo = round(liquido * rng.uniform(0.85, 1.05), 2)
            aud.append(
                Auditoria("vl_total_liquido", _fmt_moeda(liquido), _fmt_moeda(novo), quem, quando)
            )
            aud.append(
                Auditoria(
                    "vl_desconto",
                    _fmt_moeda(orc.vl_bruto - liquido),
                    _fmt_moeda(orc.vl_bruto - novo),
                    quem,
                    quando,
                )
            )
            hist.append(Historico(f"Itens revisados (versão {k + 2})", quando, quem, False))
            liquido = novo
        if orc.vl_desconto > 0:
            quando = orc.dt_cadastro + timedelta(seconds=rng.uniform(3600, janela))
            hist.append(
                Historico(
                    f"Desconto de {orc.porc_desconto:.1f}% aprovado pela gestão",
                    quando,
                    "gestao.comercial",
                    False,
                )
            )
        if orc.desfecho and orc.dt_fechamento:
            hist.append(
                Historico(f"Fechado como {orc.desfecho.lower()}", orc.dt_fechamento, quem, True)
            )
        if orc.dt_cancelou:
            hist.append(Historico("Orçamento cancelado", orc.dt_cancelou, quem, True))
        for _ in range(_poisson(rng, max(P.HISTORICO_MEDIA - len(hist), 0.5))):
            quando = orc.dt_cadastro + timedelta(seconds=rng.uniform(3600, janela))
            hist.append(
                Historico(
                    rng.choice(
                        [
                            "Contato registrado",
                            "Anexo adicionado",
                            "Observação interna",
                            "Prazo de entrega ajustado",
                            "Endereço da obra confirmado",
                        ]
                    ),
                    quando,
                    quem,
                    False,
                )
            )
        return sorted(hist, key=lambda h: h.dt_acao), sorted(aud, key=lambda a: a.dt_alterou)

    def _recebimento(self, rng: random.Random, ganho: datetime, liquido: float) -> Recebimento:
        opcoes = P.PARCELAS_OPCOES
        pesos = [w * (1.6 if (n >= 6 and liquido > 150_000) else 1.0) for n, w in opcoes]
        n = rng.choices([n for n, _ in opcoes], weights=pesos, k=1)[0]
        forma = rng.choices(
            [f for f, _, _ in FORMAS_PAGAMENTO], weights=[w for _, _, w in FORMAS_PAGAMENTO], k=1
        )[0]
        parcelas: list[Parcela] = []
        entrada = liquido if n == 1 else round(liquido * P.ENTRADA_PCT / 100, 2)
        restante = round(liquido - entrada, 2)
        for i in range(1, n + 1):
            valor = entrada if i == 1 else round(restante / (n - 1), 2)
            venc = (ganho + timedelta(days=3 if i == 1 else 30 * (i - 1) + 3)).date()
            if rng.random() < P.SHARE_PARCELA_NUNCA_PAGA:
                pago, juros = None, 0.0
            elif rng.random() < P.SHARE_PAGAMENTO_ATRASADO:
                atraso = rng.randint(10, P.ATRASO_DIAS_MAX)
                pago, juros = venc + timedelta(days=atraso), round(valor * 0.01 * atraso / 30, 2)
            else:
                pago, juros = venc + timedelta(days=rng.randint(-3, 5)), 0.0
            parcelas.append(
                Parcela(
                    i,
                    venc,
                    valor,
                    pago,
                    juros,
                    forma,
                    f"REC-{ganho.year}-{rng.randint(100000, 999999)}",
                )
            )
        return Recebimento(ganho.date(), liquido, n, forma, CONDICAO_POR_PARCELAS[n], parcelas)

    def _comissoes(self, rng: random.Random, orc: Orcamento, ganho: datetime) -> list[Comissao]:
        comp = _competencia(ganho)
        apuracao = (ganho.replace(day=1) + timedelta(days=32)).replace(day=1).date()
        primeiro_pag = None
        if orc.recebimento:
            pagos = [p.dt_pagamento for p in orc.recebimento.parcelas if p.dt_pagamento]
            primeiro_pag = min(pagos) if pagos else None
        pagamento = (
            (max(apuracao, primeiro_pag) + timedelta(days=P.DIAS_PAGAMENTO_COMISSAO))
            if primeiro_pag
            else None
        )
        base = orc.vl_liquido
        saida: list[Comissao] = []

        def add(tipo: str, uid: int | None, pid: int | None, p: float | None) -> None:
            if p is None or p <= 0:
                return
            p_real = p + 0.25 if rng.random() < P.SUJEIRA_COMISSAO_DIVERGENTE else p
            saida.append(
                Comissao(
                    tipo,
                    uid,
                    pid,
                    p_real,
                    base,
                    round(base * p_real / 100, 2),
                    comp,
                    apuracao,
                    pagamento,
                )
            )

        add("VENDEDOR", orc.vendedor.id, None, orc.p_com_vend)
        add("PARCEIRO", None, orc.parceiro_id, orc.p_com_parc)
        add("3D", orc.projetista_id, None, orc.p_com_3d)
        if orc.supervisor_id is not None:
            add("SUPERVISOR", orc.supervisor_id, None, P.COMISSAO_SUPERVISOR)
        return saida

    def _medicoes(self, rng: random.Random, orc: Orcamento) -> list[Medicao]:
        medidores = [
            u for u in self.mundo.por_cargo("MEDIDOR") if u.dt_admissao <= orc.dt_cadastro.date()
        ]
        saida: list[Medicao] = []
        if rng.random() < P.SHARE_MEDICAO:
            agendada = orc.dt_cadastro + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 6))
            realizada = (
                agendada + timedelta(days=rng.randint(0, 5)) if rng.random() < 0.95 else None
            )
            saida.append(
                Medicao(
                    rng.choice(medidores).id if medidores else None,
                    agendada,
                    realizada,
                    False,
                    rng.choice(
                        [
                            None,
                            "Pé-direito 2,90 m",
                            "Parede fora de esquadro",
                            "Medir após demolição",
                        ]
                    ),
                )
            )
        if orc.desfecho == "GANHO" and orc.dt_fechamento and rng.random() < P.SHARE_REMEDICAO_GANHO:
            agendada = orc.dt_fechamento + timedelta(days=rng.randint(2, 10))
            saida.append(
                Medicao(
                    rng.choice(medidores).id if medidores else None,
                    agendada,
                    agendada + timedelta(days=rng.randint(0, 3)),
                    True,
                    "Remedição pós-fechamento",
                )
            )
        return saida

    def _instalacao(self, rng: random.Random, orc: Orcamento, ganho: datetime) -> Instalacao:
        instaladores = [
            u for u in self.mundo.por_cargo("INSTALADOR") if u.dt_admissao <= ganho.date()
        ]
        prevista = (
            ganho + timedelta(days=rng.randint(P.INSTALACAO_LEAD_MIN, P.INSTALACAO_LEAD_MAX))
        ).date()
        inicio = prevista + timedelta(days=rng.randint(-5, 15))
        fim = inicio + timedelta(
            days=rng.randint(P.INSTALACAO_DURACAO_MIN, P.INSTALACAO_DURACAO_MAX)
        )
        problema = rng.random() < P.SHARE_INSTALACAO_PROBLEMA
        aprovado = rng.random() < 0.9
        eventos = [
            EventoInstalacao(
                "Entrega do fornecedor conferida",
                datetime.combine(inicio, datetime.min.time()) + timedelta(hours=8),
                "logistica",
                None,
            ),
            EventoInstalacao(
                "Início da montagem",
                datetime.combine(inicio, datetime.min.time()) + timedelta(hours=9),
                "instalacao",
                None,
            ),
            EventoInstalacao(
                "Vistoria parcial",
                datetime.combine(inicio + (fim - inicio) / 2, datetime.min.time())
                + timedelta(hours=15),
                "supervisao",
                None,
            ),
            EventoInstalacao(
                "Conclusão da instalação",
                datetime.combine(fim, datetime.min.time()) + timedelta(hours=17),
                "instalacao",
                None,
            ),
        ]
        for ev in rng.sample(eventos, k=2):
            ev.item_ordem = rng.choice(orc.itens).ordem if orc.itens else None
        if problema:
            eventos.append(
                EventoInstalacao(
                    "Correção solicitada pelo cliente",
                    datetime.combine(fim, datetime.min.time()) + timedelta(days=2, hours=10),
                    "pos.venda",
                    rng.choice(orc.itens).ordem if orc.itens else None,
                )
            )
        for _ in range(_poisson(rng, 2.0)):
            eventos.append(
                EventoInstalacao(
                    rng.choice(
                        [
                            "Ajuste de porta",
                            "Troca de ferragem",
                            "Retoque de pintura",
                            "Nivelamento de bancada",
                        ]
                    ),
                    datetime.combine(inicio, datetime.min.time())
                    + timedelta(
                        days=rng.randint(0, max((fim - inicio).days, 1)), hours=rng.randint(8, 17)
                    ),
                    "instalacao",
                    rng.choice(orc.itens).ordem if orc.itens else None,
                )
            )
        return Instalacao(
            rng.choice(instaladores).id if instaladores else None,
            ganho + timedelta(days=30),
            prevista,
            inicio,
            fim,
            problema,
            rng.choice(
                [
                    "Porta desalinhada",
                    "Bancada com lascado",
                    "Persiana com motor falhando",
                    "Revestimento trincado",
                ]
            )
            if problema
            else None,
            aprovado if rng.random() < 0.95 else None,
            (fim + timedelta(days=rng.randint(3, 10))) if aprovado else None,
            sorted(eventos, key=lambda e: e.dt_acao),
        )

    # ----- o orçamento inteiro -----

    def _detalhar(self, cab: Cabecalho, p_conv: float) -> Orcamento:
        rng = random.Random(f"{SEMENTE}-orc-{cab.nr}-b")
        dia = cab.dt.date()
        grupo = ORIGEM_GRUPO[cab.canal]
        parceiro_id: int | None = None
        parceiro_texto: str | None = None
        canal = cab.canal
        if grupo in ("ARQUITETOS", "CONSTRUTORAS"):
            tipo = "ESCRITORIO" if grupo == "ARQUITETOS" else "CONSTRUTORA"
            ativos = self.mundo.parceiros_ativos(tipo, dia)
            if ativos and rng.random() >= P.SHARE_PARCEIRO_SEM_CADASTRO:
                parceiro_id = rng.choices(ativos, weights=[p.peso for p in ativos], k=1)[0].id
            else:
                canal = "OUTROS"
                parceiro_texto = (
                    nomes.nome_escritorio(rng)
                    if tipo == "ESCRITORIO"
                    else nomes.nome_construtora(rng)
                )
        # cliente: recorrente ou novo
        candidatos = [c for c in self.clientes if c.dt_cadastro < cab.dt]
        cliente: Cliente
        recorrente = (canal == "IND_CLIENTE" and candidatos and rng.random() < 0.7) or (
            candidatos and rng.random() < 0.05
        )
        if recorrente:
            cliente = rng.choice(candidatos)
        else:
            cliente = self._novo_cliente(rng, cab, parceiro_id)
        endereco_idx = 1 if len(cliente.enderecos) > 1 and rng.random() < 0.8 else 0
        # itens e valores
        itens = self._itens(rng, cab, cab.dt.year)
        if (
            cab.dt.year <= 2022
            and rng.random() < P.SUJEIRA_ITEM_CANCELADO_SOMADO
            and len(itens) > 3
        ):
            itens[-1].dt_cancelou = cab.dt + timedelta(days=2)
            bruto = round(sum(i.vl_total for i in itens), 2)  # bug antigo: soma o cancelado
        else:
            if len(itens) > 5 and rng.random() < 0.10:
                itens[rng.randrange(len(itens))].dt_cancelou = cab.dt + timedelta(
                    days=rng.randint(1, 20)
                )
            bruto = round(sum(i.vl_total for i in itens if i.dt_cancelou is None), 2)
        if rng.random() < P.SHARE_SEM_DESCONTO or bruto == 0:
            porc = 0.0
        else:
            porc = round(
                min(
                    P.DESCONTO_MAX,
                    rng.uniform(P.DESCONTO_MIN, 22.0) + (4.0 if bruto > 200_000 else 0.0),
                ),
                2,
            )
        desconto = round(bruto * porc / 100, 2)
        liquido = round(bruto - desconto, 2)
        p_vend = next(p for lim, p in P.COMISSAO_VENDEDOR_FAIXAS if porc <= lim)
        p_parc = None
        if parceiro_id is not None:
            p_parc = next(p.p_comissao for p in self.mundo.parceiros if p.id == parceiro_id)
        projetista = None
        if rng.random() < P.SHARE_COM_PROJETISTA_3D:
            proj = [u for u in self.mundo.por_cargo("PROJETISTA_3D") if u.dt_admissao <= dia]
            projetista = rng.choice(proj).id if proj else None
        supervisor = None
        sups = [
            u
            for u in self.mundo.por_cargo("SUPERVISOR")
            if u.unidade_id == cab.unidade_id and u.dt_admissao <= dia
        ]
        if sups and rng.random() < P.SHARE_COM_SUPERVISOR:
            supervisor = sups[0].id
        # desfecho
        cancelou = (
            cab.dt + timedelta(days=rng.randint(1, 30))
            if rng.random() < P.SHARE_CANCELADO
            else None
        )
        desfecho: str | None = None
        fechamento: datetime | None = None
        motivo: int | None = None
        if cancelou is None:
            ganhou = cab.u_desfecho < p_conv
            if ganhou:
                dias = min(
                    _lognormal(rng, P.DIAS_FECHAR_GANHO_MEDIANA, P.DIAS_FECHAR_GANHO_SIGMA),
                    P.DIAS_FECHAR_MAX,
                )
            else:
                dias = min(
                    _lognormal(rng, P.DIAS_FECHAR_PERDIDO_MEDIANA, P.DIAS_FECHAR_PERDIDO_SIGMA),
                    P.DIAS_FECHAR_MAX,
                )
            fechamento = cab.dt + timedelta(days=dias)
            if fechamento <= HORIZONTE:
                desfecho = "GANHO" if ganhou else "PERDIDO"
                if not ganhou:
                    motivo = rng.choices(
                        [m for m, _, _ in MOTIVOS_PERDA],
                        weights=[w for _, _, w in MOTIVOS_PERDA],
                        k=1,
                    )[0]
                    if dias > 150 and rng.random() < 0.6:
                        motivo = 5  # sem retorno
            else:
                fechamento = None
        registrado = fechamento
        if fechamento is not None:
            if rng.random() < P.SUJEIRA_DATA_SENTINELA:
                registrado = SENTINELA
            elif rng.random() < P.SUJEIRA_FECHOU_ANTES_CADASTRO:
                registrado = cab.dt - timedelta(days=rng.randint(1, 600))
        forma = condicao = None
        prazo_entrega = None
        if desfecho == "GANHO" and fechamento:
            prazo_entrega = (fechamento + timedelta(days=rng.randint(60, 120))).date()
        orc = Orcamento(
            id=cab.nr,
            nr=cab.nr,
            unidade_id=cab.unidade_id,
            cliente=cliente,
            endereco_obra_idx=endereco_idx,
            tipo_id=cab.tipo_id,
            canal=canal,
            origem_id=ORIGEM_ID[canal],
            parceiro_id=parceiro_id,
            parceiro_texto=parceiro_texto,
            vendedor=cab.vendedor,
            projetista_id=projetista,
            supervisor_id=supervisor,
            dt_cadastro=cab.dt,
            ds_objetivo=(f"Indicação: {parceiro_texto}. " if parceiro_texto else "")
            + rng.choice(
                [
                    "Reforma completa do apartamento",
                    "Marcenaria da cozinha e sala",
                    "Área externa com pérgola",
                    "Cortinas e persianas para toda a casa",
                    "Suíte master e closet",
                    "Casa de praia: reforma e mobiliário",
                    "Home office e sala de estar",
                    "Revestimentos e louças dos banheiros",
                    "Varanda gourmet",
                ]
            ),
            itens=itens,
            vl_bruto=bruto,
            vl_desconto=desconto,
            porc_desconto=porc,
            vl_liquido=liquido,
            p_com_vend=p_vend,
            p_com_parc=p_parc,
            p_com_3d=P.COMISSAO_3D if projetista else None,
            forma_id=forma,
            condicao_id=condicao,
            dt_prazo_entrega=prazo_entrega,
            especial=rng.random() < 0.05,
            garantia=rng.random() < 0.03,
            dt_cancelou=cancelou,
            desfecho=desfecho,
            dt_fechamento=fechamento,
            dt_finalizou_registrado=registrado,
            motivo_perda_id=motivo,
            fases=[],
            etapas=[],
            follow_ups=[],
            historico=[],
            auditoria=[],
            recebimento=None,
            comissoes=[],
            medicoes=[],
            instalacao=None,
            fator_conversao=cab.fator,
            u_desfecho=cab.u_desfecho,
        )
        orc.fases = self._fases(rng, cab.dt, fechamento if desfecho else None, desfecho, cancelou)
        fim = fechamento or cancelou or (cab.dt + timedelta(days=180))
        orc.follow_ups = self._follow_ups(rng, cab.dt, fim, cab.vendedor)
        orc.historico, orc.auditoria = self._historico_e_auditoria(rng, orc)
        orc.medicoes = self._medicoes(rng, orc)
        if desfecho == "GANHO" and fechamento is not None and cab.tipo_id == 1 and liquido > 0:
            orc.recebimento = self._recebimento(rng, fechamento, liquido)
            orc.forma_id, orc.condicao_id = orc.recebimento.forma_id, orc.recebimento.condicao_id
            orc.comissoes = self._comissoes(rng, orc, fechamento)
            orc.etapas = self._etapas(rng, fechamento, cab.dt.year)
            orc.instalacao = self._instalacao(rng, orc, fechamento)
        return orc

    # ----- o universo -----

    def planejar(self) -> Universo:
        datas: list[datetime] = []
        for ano in P.ORCAMENTOS_POR_ANO:
            for mes in range(1, 13):
                datas.extend(_datas_cadastro(ano, mes))
        datas.sort()
        cabecalhos = [_cabecalho(self.mundo, nr, dt) for nr, dt in enumerate(datas, start=1)]
        # calibração da conversão por ano: p_i = alvo × f_i / média(f) no ano
        media_fator: dict[int, float] = {}
        for ano in P.ORCAMENTOS_POR_ANO:
            fatores = [c.fator for c in cabecalhos if c.dt.year == ano and c.tipo_id == 1]
            media_fator[ano] = sum(fatores) / max(len(fatores), 1)
        for cab in cabecalhos:
            p = P.CONVERSAO_POR_ANO[cab.dt.year] * cab.fator / media_fator[cab.dt.year]
            self.orcamentos.append(self._detalhar(cab, max(0.02, min(0.92, p))))
        return Universo(self.mundo, self.clientes, self.orcamentos)


def planejar_universo(mundo: Mundo) -> Universo:
    return Planejador(mundo).planejar()
