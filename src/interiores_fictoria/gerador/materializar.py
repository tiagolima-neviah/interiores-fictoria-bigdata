"""Materialização "como de T": transforma o universo planejado nas linhas de cada tabela
do sistema comercial, exatamente como o banco estaria no instante T.

Regras: linha existe se foi criada até T; campos que dependem do futuro (saída de fase,
conclusão de etapa, pagamento, fechamento) ficam nulos ou no estado de T. Ids de linhas
filhas são atribuídos por ordem cronológica no horizonte inteiro, então avançar T só
acrescenta ids maiores, como numa produção de verdade.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from interiores_fictoria.gerador import parametros as P
from interiores_fictoria.gerador.mundo import (
    AMBIENTES,
    CATEGORIAS,
    CONDICOES,
    FASES,
    FORMAS_PAGAMENTO,
    MOTIVOS_PERDA,
    ORIGENS,
    TIPOS_ORCAMENTO,
)
from interiores_fictoria.gerador.planejador import Orcamento, Universo

Linha = tuple[Any, ...]


@dataclass(frozen=True)
class Tabela:
    nome: str
    colunas: tuple[str, ...]
    linhas: list[Linha]
    identidade: bool = True


def _ate(valor: datetime | None, t: datetime) -> datetime | None:
    return valor if valor is not None and valor <= t else None


def _ate_data(valor: date | None, t: datetime) -> date | None:
    return valor if valor is not None and valor <= t.date() else None


def _ordenar_ids(itens: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Recebe tuplas (chave_de_ordem, linha_sem_id) e devolve linhas com id sequencial."""
    itens.sort(key=lambda x: x[0])
    return [(i, *linha) for i, (_, linha) in enumerate(itens, start=1)]


def _vivos(u: Universo, t: datetime) -> list[Orcamento]:
    return [o for o in u.orcamentos if o.dt_cadastro <= t]


# --- cadastro -------------------------------------------------------------------


def t_unidade(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (i, sigla, nome, bairro, "São Paulo", "SP", abertura, None, True)
        for i, sigla, nome, bairro, abertura in P.UNIDADES
        if abertura <= t.date()
    ]
    return Tabela(
        "cadastro.unidade",
        (
            "id",
            "sigla",
            "nome",
            "bairro",
            "cidade",
            "uf",
            "dt_abertura",
            "dt_encerramento",
            "ativo",
        ),
        linhas,
        identidade=False,
    )


def t_usuario(u: Universo, t: datetime) -> Tabela:
    linhas = []
    for us in u.mundo.usuarios:
        if us.dt_admissao > t.date():
            continue
        deslig = _ate_data(us.dt_desligamento, t)
        linhas.append(
            (
                us.id,
                us.login,
                us.nome,
                f"{us.login}@fictoria.com.br",
                us.unidade_id,
                us.cargo,
                us.cargo == "VENDEDOR",
                us.cargo == "PROJETISTA_3D",
                us.cargo == "MEDIDOR",
                us.cargo == "INSTALADOR",
                us.dt_admissao,
                deslig,
                deslig is None,
            )
        )
    return Tabela(
        "cadastro.usuario",
        (
            "id",
            "login",
            "nome",
            "email",
            "unidade_id",
            "cargo",
            "fl_vendedor",
            "fl_projetista_3d",
            "fl_medidor",
            "fl_instalador",
            "dt_admissao",
            "dt_desligamento",
            "ativo",
        ),
        linhas,
    )


def t_origem_contato(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.origem_contato",
        ("id", "codigo", "nome", "grupo", "ativo"),
        [(i, c, n, g, True) for i, c, n, g in ORIGENS],
        identidade=False,
    )


def t_parceiro(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (
            p.id,
            p.tipo,
            p.razao_social,
            p.nome_fantasia,
            p.cnpj,
            None,
            None,
            None,
            p.bairro,
            "São Paulo",
            "SP",
            p.p_comissao,
            p.vendedor_relacionamento_id,
            p.dt_inicio,
            None,
            True,
        )
        for p in u.mundo.parceiros
        if p.dt_inicio <= t.date()
    ]
    return Tabela(
        "cadastro.parceiro",
        (
            "id",
            "tipo",
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "contato_nome",
            "contato_email",
            "contato_telefone",
            "bairro",
            "cidade",
            "uf",
            "p_comissao_padrao",
            "vendedor_relacionamento_id",
            "dt_inicio_parceria",
            "dt_fim_parceria",
            "ativo",
        ),
        linhas,
    )


def t_cliente(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (
            c.id,
            c.tipo_pessoa,
            c.nome,
            c.nome_fantasia,
            c.cpf_cnpj,
            c.email,
            c.telefone,
            c.dt_nascimento,
            c.origem_id,
            c.cliente_indicador_id,
            c.parceiro_indicador_id,
            c.unidade_id,
            c.dt_cadastro,
            c.nm_cadastro,
            True,
        )
        for c in u.clientes
        if c.dt_cadastro <= t
    ]
    return Tabela(
        "cadastro.cliente",
        (
            "id",
            "tipo_pessoa",
            "nome",
            "nome_fantasia",
            "cpf_cnpj",
            "email",
            "telefone",
            "dt_nascimento",
            "origem_contato_id",
            "cliente_indicador_id",
            "parceiro_indicador_id",
            "unidade_id",
            "dt_cadastro",
            "nm_cadastro",
            "ativo",
        ),
        linhas,
    )


def endereco_ids(u: Universo) -> dict[tuple[int, int], int]:
    """Id de endereço por (cliente, índice), estável no horizonte inteiro."""
    ids: dict[tuple[int, int], int] = {}
    proximo = 1
    for c in sorted(u.clientes, key=lambda c: (c.dt_cadastro, c.id)):
        for idx, _ in enumerate(c.enderecos):
            ids[(c.id, idx)] = proximo
            proximo += 1
    return ids


def t_endereco(u: Universo, t: datetime) -> Tabela:
    ids = endereco_ids(u)
    linhas = []
    for c in u.clientes:
        if c.dt_cadastro > t:
            continue
        for idx, e in enumerate(c.enderecos):
            linhas.append(
                (
                    ids[(c.id, idx)],
                    c.id,
                    e.tipo,
                    e.logradouro,
                    e.numero,
                    e.complemento,
                    e.bairro,
                    e.cidade,
                    e.uf,
                    e.cep,
                    e.principal,
                )
            )
    linhas.sort()
    return Tabela(
        "cadastro.endereco",
        (
            "id",
            "cliente_id",
            "tipo",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "cep",
            "fl_principal",
        ),
        linhas,
    )


def t_tipo_orcamento(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.tipo_orcamento",
        ("id", "nome", "fl_conta_bi", "ativo"),
        [(i, n, bi, True) for i, n, bi in TIPOS_ORCAMENTO],
        identidade=False,
    )


def t_fase(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.fase",
        ("id", "nome", "grupo", "ordem", "ativo"),
        [(i, n, g, o, True) for i, n, g, o in FASES],
        identidade=False,
    )


def t_motivo_perda(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.motivo_perda",
        ("id", "nome", "ativo"),
        [(i, n, True) for i, n, _ in MOTIVOS_PERDA],
        identidade=False,
    )


def t_status_etapa(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (i, nome, i, prazo, nome in ("CORREÇÃO", "APROVAÇÃO PÓS VENDA"), True)
        for i, (nome, prazo, _) in enumerate(P.ETAPAS_EXECUCAO, start=1)
    ]
    return Tabela(
        "cadastro.status_etapa",
        ("id", "nome", "ordem", "qtd_dias_limite", "fl_pos_venda", "ativo"),
        linhas,
        identidade=False,
    )


def t_ambiente(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.ambiente",
        ("id", "nome"),
        [(i, n) for i, n in enumerate(AMBIENTES, start=1)],
        identidade=False,
    )


def t_categoria_item(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.categoria_item",
        ("id", "nome", "fl_servico"),
        [(i, n, s) for i, n, s, _, _, _ in CATEGORIAS],
        identidade=False,
    )


def t_fornecedor(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (
            f.id,
            f.razao_social,
            f.nome_fantasia,
            f.cnpj,
            f.categoria_id,
            "São Paulo",
            "SP",
            f.prazo_dias,
            True,
        )
        for f in u.mundo.fornecedores
    ]
    return Tabela(
        "cadastro.fornecedor",
        (
            "id",
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "categoria_item_id",
            "cidade",
            "uf",
            "prazo_entrega_dias",
            "ativo",
        ),
        linhas,
    )


def t_item_catalogo(u: Universo, t: datetime) -> Tabela:
    linhas = [
        (
            i.id,
            i.codigo,
            i.descricao,
            i.categoria_id,
            i.fornecedor_id,
            i.unidade_medida,
            i.vl_referencia,
            i.vl_custo_referencia,
            i.fl_gera_comissao,
            i.fl_gera_comissao_3d,
            i.dt_cadastro,
            True,
        )
        for i in u.mundo.itens
        if i.dt_cadastro <= t
    ]
    return Tabela(
        "cadastro.item_catalogo",
        (
            "id",
            "codigo",
            "descricao",
            "categoria_item_id",
            "fornecedor_id",
            "unidade_medida",
            "vl_referencia",
            "vl_custo_referencia",
            "fl_gera_comissao",
            "fl_gera_comissao_3d",
            "dt_cadastro",
            "ativo",
        ),
        linhas,
    )


def t_forma_pagamento(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.forma_pagamento",
        ("id", "nome", "ativo"),
        [(i, n, True) for i, n, _ in FORMAS_PAGAMENTO],
        identidade=False,
    )


def t_condicao_parcelamento(u: Universo, t: datetime) -> Tabela:
    return Tabela(
        "cadastro.condicao_parcelamento",
        ("id", "nome", "nr_parcelas", "p_entrada", "intervalo_dias", "ativo"),
        [(i, n, np_, pe, 30, True) for i, n, np_, pe in CONDICOES],
        identidade=False,
    )


# --- comercial ------------------------------------------------------------------


def _fase_em(o: Orcamento, t: datetime) -> int:
    atual = o.fases[0].fase_id
    for f in o.fases:
        if f.dt_entrada <= t:
            atual = f.fase_id
    return atual


def t_orcamento(u: Universo, t: datetime) -> Tabela:
    end_ids = endereco_ids(u)
    linhas = []
    for o in _vivos(u, t):
        fechado = o.dt_fechamento is not None and o.dt_fechamento <= t
        finalizou = o.dt_finalizou_registrado if fechado else None
        endereco = (
            end_ids.get((o.cliente.id, o.endereco_obra_idx))
            if o.endereco_obra_idx is not None
            else None
        )
        linhas.append(
            (
                o.id,
                1000 + o.nr,
                o.unidade_id,
                o.cliente.id,
                endereco,
                o.tipo_id,
                _fase_em(o, t),
                o.origem_id,
                o.parceiro_id,
                o.vendedor.id,
                o.projetista_id,
                o.supervisor_id,
                None,
                o.ds_objetivo,
                o.dt_cadastro,
                o.vendedor.login,
                finalizou,
                o.vendedor.login if fechado else None,
                o.motivo_perda_id if fechado else None,
                _ate(o.dt_cancelou, t),
                o.vendedor.login if _ate(o.dt_cancelou, t) else None,
                o.vl_bruto,
                o.vl_desconto,
                o.porc_desconto,
                o.vl_liquido,
                o.p_com_vend,
                round(o.vl_liquido * (o.p_com_vend or 0) / 100, 2),
                o.p_com_parc,
                round(o.vl_liquido * (o.p_com_parc or 0) / 100, 2) if o.p_com_parc else None,
                o.p_com_3d,
                round(o.vl_liquido * (o.p_com_3d or 0) / 100, 2) if o.p_com_3d else None,
                o.forma_id if fechado else None,
                o.condicao_id if fechado else None,
                o.dt_prazo_entrega if fechado else None,
                o.especial,
                o.garantia,
                o.endereco_obra_idx == 1,
            )
        )
    return Tabela(
        "comercial.orcamento",
        (
            "id",
            "nr_orcamento",
            "unidade_id",
            "cliente_id",
            "endereco_obra_id",
            "tipo_orcamento_id",
            "fase_id",
            "origem_contato_id",
            "parceiro_id",
            "vendedor_id",
            "projetista_3d_id",
            "supervisor_id",
            "orcamento_ref_id",
            "ds_objetivo",
            "dt_cadastro",
            "nm_cadastro",
            "dt_finalizou",
            "nm_finalizou",
            "motivo_perda_id",
            "dt_cancelou",
            "nm_cancelou",
            "vl_total_bruto",
            "vl_desconto",
            "porc_desconto",
            "vl_total_liquido",
            "p_comissao_vendedor",
            "vl_comissao_vendedor",
            "p_comissao_parceiro",
            "vl_comissao_parceiro",
            "p_comissao_3d",
            "vl_comissao_3d",
            "forma_pagamento_id",
            "condicao_parcelamento_id",
            "dt_prazo_entrega",
            "fl_pedido_especial",
            "fl_garantia",
            "fl_endereco_entrega_diferente",
        ),
        linhas,
    )


def item_ids(u: Universo) -> dict[tuple[int, int], int]:
    ids: dict[tuple[int, int], int] = {}
    proximo = 1
    for o in sorted(u.orcamentos, key=lambda o: (o.dt_cadastro, o.id)):
        for it in o.itens:
            ids[(o.id, it.ordem)] = proximo
            proximo += 1
    return ids


def t_orcamento_item(u: Universo, t: datetime) -> Tabela:
    ids = item_ids(u)
    linhas = []
    for o in _vivos(u, t):
        for it in o.itens:
            linhas.append(
                (
                    ids[(o.id, it.ordem)],
                    o.id,
                    it.ambiente_id,
                    it.item_id,
                    it.descricao,
                    it.qtd,
                    it.vl_unitario,
                    it.vl_custo,
                    it.vl_markup,
                    it.vl_total,
                    it.ordem,
                    o.dt_cadastro,
                    o.vendedor.login,
                    _ate(it.dt_cancelou, t),
                    o.vendedor.login if _ate(it.dt_cancelou, t) else None,
                    it.gera_comissao,
                    _ate(o.dt_fechamento, t) if o.desfecho == "GANHO" else None,
                    _ate(o.dt_fechamento, t) if o.desfecho == "GANHO" and o.etapas else None,
                    None,
                )
            )
    linhas.sort()
    return Tabela(
        "comercial.orcamento_item",
        (
            "id",
            "orcamento_id",
            "ambiente_id",
            "item_catalogo_id",
            "ds_descricao",
            "qtd",
            "vl_unitario",
            "vl_custo",
            "vl_markup",
            "vl_total",
            "ordem",
            "dt_cadastro",
            "nm_cadastro",
            "dt_cancelou",
            "nm_cancelou",
            "fl_gera_comissao",
            "dt_liberou_projeto",
            "dt_liberou_producao",
            "p_instalacao",
        ),
        linhas,
    )


def t_orcamento_fase_hist(u: Universo, t: datetime) -> Tabela:
    itens = []
    for o in u.orcamentos:
        for f in o.fases:
            itens.append(
                (
                    (f.dt_entrada, o.id, f.fase_id),
                    (o.id, f.fase_id, f.dt_entrada, f.dt_saida, o.vendedor.login),
                )
            )
    linhas = [
        (i, oid, fid, ent, _ate(sai, t), quem)
        for i, oid, fid, ent, sai, quem in _ordenar_ids(itens)
        if ent <= t
    ]
    return Tabela(
        "comercial.orcamento_fase_hist",
        ("id", "orcamento_id", "fase_id", "dt_entrada", "dt_saida", "nm_usuario"),
        linhas,
    )


def t_orcamento_etapa(u: Universo, t: datetime) -> Tabela:
    itens = []
    for o in u.orcamentos:
        for e in o.etapas:
            itens.append(
                (
                    (e.dt_cadastro, o.id, e.status_id),
                    (
                        o.id,
                        e.status_id,
                        e.dt_cadastro,
                        "sistema",
                        e.dt_limite,
                        e.dt_concluiu,
                        e.manual,
                    ),
                )
            )
    linhas = []
    for i, oid, sid, cad, quem, lim, concl, manual in _ordenar_ids(itens):
        if cad > t:
            continue
        concluiu = _ate(concl, t)
        linhas.append(
            (
                i,
                oid,
                sid,
                cad,
                quem,
                lim,
                concluiu,
                "operacao" if concluiu else None,
                None,
                None,
                manual,
                manual and concluiu is not None,
            )
        )
    return Tabela(
        "comercial.orcamento_etapa",
        (
            "id",
            "orcamento_id",
            "status_etapa_id",
            "dt_cadastro",
            "nm_cadastro",
            "dt_limite",
            "dt_concluiu",
            "nm_concluiu",
            "dt_cancelou",
            "nm_cancelou",
            "fl_manual",
            "fl_concluiu_manual",
        ),
        linhas,
    )


def t_follow_up(u: Universo, t: datetime) -> Tabela:
    itens = [
        ((f.dt_lanc, o.id, k), (o.id, f.usuario_id, f.dt_lanc, f.tipo, f.obs, f.proximo))
        for o in u.orcamentos
        for k, f in enumerate(o.follow_ups)
    ]
    linhas = [linha for linha in _ordenar_ids(itens) if linha[3] <= t]
    return Tabela(
        "comercial.follow_up",
        (
            "id",
            "orcamento_id",
            "usuario_id",
            "dt_lanc",
            "tipo_contato",
            "ds_obs",
            "dt_proximo_contato",
        ),
        linhas,
    )


def t_orcamento_historico(u: Universo, t: datetime) -> Tabela:
    itens = [
        ((h.dt_acao, o.id, k), (o.id, h.ds_acao, h.dt_acao, h.nm_acao, h.fl_log))
        for o in u.orcamentos
        for k, h in enumerate(o.historico)
    ]
    linhas = [linha for linha in _ordenar_ids(itens) if linha[3] <= t]
    return Tabela(
        "comercial.orcamento_historico",
        ("id", "orcamento_id", "ds_acao", "dt_acao", "nm_acao", "fl_log"),
        linhas,
    )


def t_auditoria_orcamento(u: Universo, t: datetime) -> Tabela:
    itens = [
        (
            (a.dt_alterou, o.id, k),
            (o.id, a.ds_campo, a.vl_antigo, a.vl_novo, a.nm_alterou, a.dt_alterou),
        )
        for o in u.orcamentos
        for k, a in enumerate(o.auditoria)
    ]
    linhas = [linha for linha in _ordenar_ids(itens) if linha[6] <= t]
    return Tabela(
        "comercial.auditoria_orcamento",
        ("id", "orcamento_id", "ds_campo", "vl_antigo", "vl_novo", "nm_alterou", "dt_alterou"),
        linhas,
    )


# --- financeiro -----------------------------------------------------------------


def recebimento_ids(u: Universo) -> dict[int, int]:
    ordem = sorted(
        (o for o in u.orcamentos if o.recebimento),
        key=lambda o: (o.recebimento.dt_emissao if o.recebimento else date.min, o.id),
    )
    return {o.id: i for i, o in enumerate(ordem, start=1)}


def t_recebimento(u: Universo, t: datetime) -> Tabela:
    ids = recebimento_ids(u)
    linhas = []
    for o in u.orcamentos:
        r = o.recebimento
        if r is None or r.dt_emissao > t.date():
            continue
        linhas.append(
            (
                ids[o.id],
                o.id,
                r.dt_emissao,
                r.vl_total,
                r.nr_parcelas,
                r.forma_id,
                r.condicao_id,
                "financeiro",
                None,
                None,
            )
        )
    linhas.sort()
    return Tabela(
        "financeiro.recebimento",
        (
            "id",
            "orcamento_id",
            "dt_emissao",
            "vl_total",
            "nr_parcelas",
            "forma_pagamento_id",
            "condicao_parcelamento_id",
            "nm_usuario",
            "dt_cancelamento",
            "motivo_cancelamento",
        ),
        linhas,
    )


def parcela_ids(u: Universo) -> dict[tuple[int, int], int]:
    rids = recebimento_ids(u)
    ids: dict[tuple[int, int], int] = {}
    proximo = 1
    for o in sorted((o for o in u.orcamentos if o.recebimento), key=lambda o: rids[o.id]):
        assert o.recebimento is not None
        for p in o.recebimento.parcelas:
            ids[(o.id, p.nr)] = proximo
            proximo += 1
    return ids


def t_parcela(u: Universo, t: datetime) -> Tabela:
    rids, pids = recebimento_ids(u), parcela_ids(u)
    linhas = []
    for o in u.orcamentos:
        r = o.recebimento
        if r is None or r.dt_emissao > t.date():
            continue
        for p in r.parcelas:
            pago = p.dt_pagamento is not None and p.dt_pagamento <= t.date()
            linhas.append(
                (
                    pids[(o.id, p.nr)],
                    rids[o.id],
                    p.nr,
                    p.dt_vencimento,
                    p.valor,
                    pago,
                    p.nr_documento,
                    None,
                )
            )
    linhas.sort()
    return Tabela(
        "financeiro.parcela",
        (
            "id",
            "recebimento_id",
            "nr_parcela",
            "dt_vencimento",
            "vl_parcela",
            "fl_pago",
            "nr_documento",
            "dt_cancelamento",
        ),
        linhas,
    )


def t_pagamento(u: Universo, t: datetime) -> Tabela:
    pids = parcela_ids(u)
    itens = []
    for o in u.orcamentos:
        r = o.recebimento
        if r is None:
            continue
        for p in r.parcelas:
            if p.dt_pagamento is None:
                continue
            itens.append(
                (
                    (p.dt_pagamento, o.id, p.nr),
                    (
                        pids[(o.id, p.nr)],
                        p.dt_pagamento,
                        round(p.valor + p.vl_juros, 2),
                        p.vl_juros,
                        0.0,
                        p.forma_id,
                        "financeiro",
                    ),
                )
            )
    linhas = [linha for linha in _ordenar_ids(itens) if linha[2] <= t.date()]
    return Tabela(
        "financeiro.pagamento",
        (
            "id",
            "parcela_id",
            "dt_pagamento",
            "vl_pago",
            "vl_juros",
            "vl_desconto",
            "forma_pagamento_id",
            "nm_usuario",
        ),
        linhas,
    )


def t_comissao(u: Universo, t: datetime) -> Tabela:
    itens = []
    for o in u.orcamentos:
        for k, c in enumerate(o.comissoes):
            itens.append(
                (
                    (c.dt_apuracao, o.id, k),
                    (
                        o.id,
                        c.tipo,
                        c.usuario_id,
                        c.parceiro_id,
                        c.p,
                        c.vl_base,
                        c.vl,
                        c.competencia,
                        c.dt_apuracao,
                        c.dt_pagamento,
                    ),
                )
            )
    linhas = []
    for i, oid, tipo, uid, pid, p, base, vl, comp, apur, pag in _ordenar_ids(itens):
        if apur > t.date():
            continue
        pago = _ate_data(pag, t)
        linhas.append((i, oid, tipo, uid, pid, p, base, vl, comp, apur, pago, pago is not None))
    return Tabela(
        "financeiro.comissao",
        (
            "id",
            "orcamento_id",
            "tipo",
            "usuario_id",
            "parceiro_id",
            "p_comissao",
            "vl_base",
            "vl_comissao",
            "competencia",
            "dt_apuracao",
            "dt_pagamento",
            "fl_pago",
        ),
        linhas,
    )


# --- obra -----------------------------------------------------------------------


def t_medicao(u: Universo, t: datetime) -> Tabela:
    itens = [
        (
            (m.dt_agendada, o.id, k),
            (o.id, m.medidor_id, m.dt_agendada, m.dt_realizada, m.remedicao, m.obs),
        )
        for o in u.orcamentos
        for k, m in enumerate(o.medicoes)
    ]
    linhas = [
        (i, oid, mid, ag, _ate(re, t), rem, obs)
        for i, oid, mid, ag, re, rem, obs in _ordenar_ids(itens)
        if ag <= t
    ]
    return Tabela(
        "obra.medicao",
        (
            "id",
            "orcamento_id",
            "medidor_id",
            "dt_agendada",
            "dt_realizada",
            "fl_remedicao",
            "ds_obs",
        ),
        linhas,
    )


def instalacao_ids(u: Universo) -> dict[int, int]:
    ordem = sorted(
        (o for o in u.orcamentos if o.instalacao),
        key=lambda o: (o.instalacao.dt_criacao if o.instalacao else datetime.min, o.id),
    )
    return {o.id: i for i, o in enumerate(ordem, start=1)}


def t_instalacao(u: Universo, t: datetime) -> Tabela:
    ids = instalacao_ids(u)
    linhas = []
    for o in u.orcamentos:
        ins = o.instalacao
        if ins is None or ins.dt_criacao > t:
            continue
        fim = _ate_data(ins.dt_fim, t)
        aprov = _ate_data(ins.dt_aprovacao, t)
        linhas.append(
            (
                ids[o.id],
                o.id,
                ins.instalador_id,
                ins.dt_prevista,
                _ate_data(ins.dt_inicio, t),
                fim,
                ins.problema if fim else False,
                ins.ds_problema if fim and ins.problema else None,
                ins.aprovado if aprov else None,
                aprov,
            )
        )
    linhas.sort()
    return Tabela(
        "obra.instalacao",
        (
            "id",
            "orcamento_id",
            "instalador_id",
            "dt_prevista",
            "dt_inicio",
            "dt_fim",
            "fl_problema",
            "ds_problema",
            "fl_aprovado_pos_venda",
            "dt_aprovacao_pos_venda",
        ),
        linhas,
    )


def t_instalacao_historico(u: Universo, t: datetime) -> Tabela:
    ids, iids = instalacao_ids(u), item_ids(u)
    itens = []
    for o in u.orcamentos:
        ins = o.instalacao
        if ins is None:
            continue
        for k, ev in enumerate(ins.eventos):
            item = iids.get((o.id, ev.item_ordem)) if ev.item_ordem is not None else None
            itens.append(
                ((ev.dt_acao, o.id, k), (ids[o.id], item, ev.ds_acao, ev.dt_acao, ev.nm_acao))
            )
    linhas = [linha for linha in _ordenar_ids(itens) if linha[4] <= t]
    return Tabela(
        "obra.instalacao_historico",
        ("id", "instalacao_id", "orcamento_item_id", "ds_acao", "dt_acao", "nm_acao"),
        linhas,
    )


# Ordem de carga: pais antes de filhos (FKs).
TABELAS: Sequence[Callable[[Universo, datetime], Tabela]] = (
    t_unidade,
    t_usuario,
    t_origem_contato,
    t_parceiro,
    t_cliente,
    t_endereco,
    t_tipo_orcamento,
    t_fase,
    t_motivo_perda,
    t_status_etapa,
    t_ambiente,
    t_categoria_item,
    t_fornecedor,
    t_item_catalogo,
    t_forma_pagamento,
    t_condicao_parcelamento,
    t_orcamento,
    t_orcamento_item,
    t_orcamento_fase_hist,
    t_orcamento_etapa,
    t_follow_up,
    t_orcamento_historico,
    t_auditoria_orcamento,
    t_recebimento,
    t_parcela,
    t_pagamento,
    t_comissao,
    t_medicao,
    t_instalacao,
    t_instalacao_historico,
)
