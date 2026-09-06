"""O mundo cadastral da Fictoria: unidades, pessoas, catálogos, parceiros, fornecedores e itens.

Tudo determinístico a partir da semente. As entidades trazem a data em que passam a
existir (abertura, admissão, início de parceria, cadastro), para a materialização
"como de T" incluir só o que já existia em T.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from interiores_fictoria.gerador import SEMENTE, nomes
from interiores_fictoria.gerador import parametros as P

# --- Catálogos fixos ------------------------------------------------------------

ORIGENS: list[tuple[int, str, str, str]] = [
    # id, codigo, nome, grupo
    (1, "WHATSAPP", "WhatsApp", "CANAL_PROPRIO"),
    (2, "INSTAGRAM", "Instagram", "CANAL_PROPRIO"),
    (3, "FACEBOOK", "Facebook", "CANAL_PROPRIO"),
    (4, "SAC", "SAC / Showroom", "CANAL_PROPRIO"),
    (5, "ANUNCIO", "Anúncio", "CANAL_PROPRIO"),
    (6, "IND_CLIENTE", "Indicação de cliente", "INDICACAO_CLIENTE"),
    (7, "ARQUITETO", "Indicação de arquiteto", "ARQUITETOS"),
    (8, "CONSTRUTORA", "Indicação de construtora", "CONSTRUTORAS"),
    (9, "OUTROS", "Outros", "OUTROS"),
]
ORIGEM_ID: dict[str, int] = {codigo: i for i, codigo, _, _ in ORIGENS}
ORIGEM_GRUPO: dict[str, str] = {codigo: grupo for _, codigo, _, grupo in ORIGENS}

TIPOS_ORCAMENTO: list[tuple[int, str, bool]] = [
    (1, "VENDA", True),
    (2, "ASSISTÊNCIA TÉCNICA", False),
    (3, "GARANTIA", False),
    (4, "CORTESIA", False),
]

FASES: list[tuple[int, str, str, int]] = [
    (1, "AGENDAR VISITA AO SHOWROOM", "ABERTO", 1),
    (2, "VISITA LOCAL COM MEDIDOR TÉCNICO", "ABERTO", 2),
    (3, "MAPEAMENTO DAS NECESSIDADES", "ABERTO", 3),
    (4, "EM ANDAMENTO", "ABERTO", 4),
    (5, "NEGOCIAÇÃO", "ABERTO", 5),
    (6, "FECHADO/GANHO", "GANHO", 6),
    (7, "FECHADO/PERDIDO", "PERDIDO", 7),
]
FASE_GANHO, FASE_PERDIDO = 6, 7

MOTIVOS_PERDA: list[tuple[int, str, float]] = [
    (1, "Preço", 0.28),
    (2, "Prazo", 0.08),
    (3, "Concorrência", 0.15),
    (4, "Adiou a obra", 0.14),
    (5, "Sem retorno", 0.27),
    (6, "Escopo mudou", 0.05),
    (7, "Outros", 0.03),
]

AMBIENTES: list[str] = [
    "Sala de estar",
    "Sala de jantar",
    "Cozinha",
    "Suíte master",
    "Quarto",
    "Home office",
    "Varanda gourmet",
    "Área externa",
    "Banheiro",
    "Lavabo",
    "Closet",
    "Lavanderia",
    "Área de piscina",
    "Hall de entrada",
]

CATEGORIAS: list[tuple[int, str, bool, float, float, float]] = [
    # id, nome, servico, peso no mix, custo/valor min, custo/valor max
    (1, "Marcenaria e planejados", False, 30, 0.55, 0.65),
    (2, "Reforma e mão de obra", True, 15, 0.60, 0.70),
    (3, "Revestimentos", False, 15, 0.58, 0.68),
    (4, "Louças e metais", False, 10, 0.60, 0.70),
    (5, "Cortinas e persianas", False, 12, 0.50, 0.62),
    (6, "Proteção solar e pérgolas", False, 8, 0.55, 0.65),
    (7, "Projeto", True, 5, 0.40, 0.55),
    (8, "Instalação", True, 5, 0.55, 0.70),
]

ITENS_POR_CATEGORIA: dict[int, list[tuple[str, str, float]]] = {
    1: [
        ("Armário planejado sob medida", "ML", 2_800),
        ("Painel ripado em madeira", "M2", 1_450),
        ("Bancada de apoio em laca", "UN", 6_500),
        ("Closet completo", "VB", 48_000),
        ("Cozinha planejada linha premium", "VB", 65_000),
        ("Estante com iluminação embutida", "ML", 3_900),
        ("Cabeceira estofada sob medida", "UN", 7_800),
        ("Painel de TV com nicho", "UN", 9_200),
        ("Mesa de jantar em madeira maciça", "UN", 14_500),
        ("Marcenaria de varanda gourmet", "VB", 32_000),
    ],
    2: [
        ("Demolição e remoção de entulho", "M2", 180),
        ("Alvenaria e regularização", "M2", 420),
        ("Elétrica completa do ambiente", "VB", 9_800),
        ("Hidráulica completa do ambiente", "VB", 8_600),
        ("Gesso acartonado com sanca", "M2", 260),
        ("Pintura premium", "M2", 95),
        ("Gerenciamento de obra", "H", 380),
        ("Impermeabilização", "M2", 210),
    ],
    3: [
        ("Porcelanato grande formato", "M2", 480),
        ("Mármore Calacatta", "M2", 2_900),
        ("Quartzito exótico", "M2", 3_400),
        ("Piso de madeira engenheirada", "M2", 690),
        ("Pedra natural para área externa", "M2", 750),
        ("Revestimento cimentício", "M2", 320),
        ("Mosaico artesanal", "M2", 1_100),
    ],
    4: [
        ("Cuba esculpida em pedra", "UN", 4_200),
        ("Metais linha premium (conjunto)", "VB", 12_800),
        ("Bacia com caixa acoplada premium", "UN", 6_900),
        ("Banheira de imersão", "UN", 18_500),
        ("Chuveiro de teto com cromoterapia", "UN", 7_400),
        ("Torneira monocomando premium", "UN", 3_600),
    ],
    5: [
        ("Cortina em linho com blackout", "M2", 890),
        ("Persiana rolô tela solar", "M2", 640),
        ("Persiana romana em tecido", "M2", 780),
        ("Persiana de madeira", "M2", 1_150),
        ("Cortina motorizada", "M2", 1_600),
        ("Cortina celular termoacústica", "M2", 1_350),
    ],
    6: [
        ("Pérgola bioclimática", "M2", 5_800),
        ("Cobertura retrátil", "M2", 3_900),
        ("Toldo de avanço motorizado", "M2", 1_900),
        ("Tela solar externa", "M2", 1_250),
        ("Guarda-corpo em vidro", "ML", 2_100),
    ],
    7: [
        ("Projeto executivo de interiores", "VB", 18_000),
        ("Projeto 3D por ambiente", "UN", 2_400),
        ("Projeto luminotécnico", "VB", 7_500),
        ("Consultoria de acabamentos", "H", 450),
    ],
    8: [
        ("Instalação de marcenaria", "H", 220),
        ("Instalação de cortinas e persianas", "UN", 380),
        ("Instalação de pérgola", "VB", 6_500),
        ("Assentamento de revestimento", "M2", 190),
    ],
}

FORMAS_PAGAMENTO: list[tuple[int, str, float]] = [
    (1, "PIX", 0.30),
    (2, "TRANSFERÊNCIA", 0.25),
    (3, "BOLETO", 0.15),
    (4, "CARTÃO DE CRÉDITO", 0.15),
    (5, "FINANCIAMENTO", 0.10),
    (6, "CHEQUE", 0.05),
]

CONDICOES: list[tuple[int, str, int, float]] = [
    (1, "À vista", 1, 100.0),
    (2, "Entrada + 2", 3, 30.0),
    (3, "Entrada + 5", 6, 30.0),
    (4, "Entrada + 9", 10, 30.0),
    (5, "Entrada + 11", 12, 30.0),
]
CONDICAO_POR_PARCELAS: dict[int, int] = {n: i for i, _, n, _ in CONDICOES}

FORNECEDORES_POR_CATEGORIA = {1: 12, 2: 8, 3: 10, 4: 8, 5: 9, 6: 6, 7: 3, 8: 4}


# --- Entidades geradas ----------------------------------------------------------


@dataclass
class Usuario:
    id: int
    login: str
    nome: str
    unidade_id: int
    cargo: str
    dt_admissao: date
    dt_desligamento: date | None
    perfil: str = "M"
    forca: float = 1.0  # peso relativo de vendas


@dataclass
class Parceiro:
    id: int
    tipo: str
    razao_social: str
    nome_fantasia: str
    cnpj: str
    bairro: str
    p_comissao: float
    dt_inicio: date
    vendedor_relacionamento_id: int | None
    peso: float


@dataclass
class Fornecedor:
    id: int
    razao_social: str
    nome_fantasia: str
    cnpj: str
    categoria_id: int
    prazo_dias: int


@dataclass
class ItemCatalogo:
    id: int
    codigo: str
    descricao: str
    categoria_id: int
    fornecedor_id: int | None
    unidade_medida: str
    vl_referencia: float
    vl_custo_referencia: float
    fl_gera_comissao: bool
    fl_gera_comissao_3d: bool
    dt_cadastro: datetime


@dataclass
class Mundo:
    usuarios: list[Usuario] = field(default_factory=list)
    parceiros: list[Parceiro] = field(default_factory=list)
    fornecedores: list[Fornecedor] = field(default_factory=list)
    itens: list[ItemCatalogo] = field(default_factory=list)

    def vendedores(self) -> list[Usuario]:
        return [u for u in self.usuarios if u.cargo == "VENDEDOR"]

    def por_cargo(self, cargo: str) -> list[Usuario]:
        return [u for u in self.usuarios if u.cargo == cargo]

    def vendedores_ativos(self, unidade_id: int, dia: date) -> list[Usuario]:
        return [
            u
            for u in self.vendedores()
            if u.unidade_id == unidade_id
            and u.dt_admissao <= dia
            and (u.dt_desligamento is None or u.dt_desligamento >= dia)
        ]

    def parceiros_ativos(self, tipo: str, dia: date) -> list[Parceiro]:
        return [p for p in self.parceiros if p.tipo == tipo and p.dt_inicio <= dia]


def _usuarios(rng: random.Random) -> list[Usuario]:
    usuarios: list[Usuario] = []
    proximo = 1

    def novo(
        cargo: str, unidade: int, admissao: date, deslig: date | None = None, perfil: str = "M"
    ) -> Usuario:
        nonlocal proximo
        nome = nomes.nome_pessoa(rng)
        u = Usuario(
            proximo,
            nomes.login(nome, proximo),
            nome,
            unidade,
            cargo,
            admissao,
            deslig,
            perfil,
            forca=rng.lognormvariate(0.0, 0.35),
        )
        usuarios.append(u)
        proximo += 1
        return u

    for unidade, admissao, deslig, perfil in P.VENDEDORES:
        novo("VENDEDOR", unidade, admissao, deslig, perfil)
    # Gestão e apoio: gestores desde a abertura; supervisores a partir da nova gestão (2024).
    novo("GESTOR", 1, date(2021, 1, 4))
    novo("GESTOR", 1, date(2024, 1, 8))
    novo("SUPERVISOR", 1, date(2024, 1, 8))
    novo("SUPERVISOR", 2, date(2024, 1, 8))
    novo("SUPERVISOR", 3, date(2025, 2, 3))
    for unidade, admissao in [
        (1, date(2021, 1, 4)),
        (1, date(2022, 6, 1)),
        (2, date(2023, 3, 6)),
        (3, date(2025, 2, 3)),
    ]:
        novo("PROJETISTA_3D", unidade, admissao)
    for unidade, admissao in [
        (1, date(2021, 1, 4)),
        (1, date(2021, 1, 4)),
        (2, date(2023, 3, 6)),
        (1, date(2024, 4, 1)),
        (3, date(2025, 2, 3)),
    ]:
        novo("MEDIDOR", unidade, admissao)
    for unidade, admissao in [
        (1, date(2021, 1, 4)),
        (1, date(2021, 1, 4)),
        (1, date(2021, 6, 1)),
        (2, date(2023, 3, 6)),
        (2, date(2023, 3, 6)),
        (1, date(2024, 2, 1)),
        (3, date(2025, 2, 3)),
        (3, date(2025, 2, 3)),
    ]:
        novo("INSTALADOR", unidade, admissao)
    for unidade, admissao in [(1, date(2021, 1, 4)), (2, date(2023, 3, 6)), (3, date(2025, 2, 3))]:
        novo("ADMINISTRATIVO", unidade, admissao)
    return usuarios


def _data_no_ano(rng: random.Random, ano: int) -> date:
    inicio = date(ano, 1, 1)
    return inicio + timedelta(days=rng.randint(0, 364))


def _parceiros(rng: random.Random, usuarios: list[Usuario]) -> list[Parceiro]:
    vendedores = [u for u in usuarios if u.cargo == "VENDEDOR"]
    parceiros: list[Parceiro] = []
    anos = list(P.ENTRADA_PARCEIROS_POR_ANO)
    pesos_anos = [P.ENTRADA_PARCEIROS_POR_ANO[a] for a in anos]
    proximo = 1
    for tipo, n, comissao in [
        ("ESCRITORIO", P.N_ESCRITORIOS, P.COMISSAO_PADRAO_ESCRITORIO),
        ("CONSTRUTORA", P.N_CONSTRUTORAS, P.COMISSAO_PADRAO_CONSTRUTORA),
    ]:
        for k in range(n):
            ano = rng.choices(anos, weights=pesos_anos, k=1)[0]
            inicio = max(_data_no_ano(rng, ano), date(2021, 1, 4))
            fantasia = (
                nomes.nome_escritorio(rng) if tipo == "ESCRITORIO" else nomes.nome_construtora(rng)
            )
            razao = f"{fantasia} Ltda"
            ativos = [v for v in vendedores if v.dt_admissao <= inicio]
            relacionamento = rng.choice(ativos).id if ativos and rng.random() < 0.7 else None
            p_com = round(max(2.0, min(8.0, rng.gauss(comissao, 1.0))), 2)
            peso = 1.0 / ((k + 1) ** P.ZIPF_PARCEIROS)  # cauda longa
            parceiros.append(
                Parceiro(
                    proximo,
                    tipo,
                    razao,
                    fantasia,
                    nomes.cnpj(rng),
                    nomes.bairro_sp(rng),
                    p_com,
                    inicio,
                    relacionamento,
                    peso,
                )
            )
            proximo += 1
    return parceiros


def _fornecedores(rng: random.Random) -> list[Fornecedor]:
    saida: list[Fornecedor] = []
    proximo = 1
    for categoria_id, n in FORNECEDORES_POR_CATEGORIA.items():
        for _ in range(n):
            ramo = rng.choice(["Indústria", "Comercial", "Design", "Acabamentos", "Marcenaria"])
            fantasia = f"{rng.choice(nomes.SOBRENOMES)} {ramo}"
            saida.append(
                Fornecedor(
                    proximo,
                    f"{fantasia} Ltda",
                    fantasia,
                    nomes.cnpj(rng),
                    categoria_id,
                    rng.choice([15, 20, 25, 30, 40, 45]),
                )
            )
            proximo += 1
    return saida


def _itens(rng: random.Random, fornecedores: list[Fornecedor]) -> list[ItemCatalogo]:
    itens: list[ItemCatalogo] = []
    proximo = 1
    for categoria_id, _nome, servico, _peso, cv_min, cv_max in CATEGORIAS:
        forn_cat = [f for f in fornecedores if f.categoria_id == categoria_id]
        modelos = ITENS_POR_CATEGORIA[categoria_id]
        # Cada modelo ganha variantes (linhas, acabamentos) para o catálogo ter ~350 itens.
        variantes = [
            "",
            " linha Classic",
            " linha Signature",
            " linha Studio",
            " acabamento fosco",
            " acabamento brilho",
            " premium",
            " essencial",
        ]
        for descricao, um, valor in modelos:
            for v in rng.sample(variantes, k=rng.randint(3, 6)):
                fator = rng.uniform(0.85, 1.25)
                vl_ref = round(valor * fator, 2)
                cv = rng.uniform(cv_min, cv_max)
                itens.append(
                    ItemCatalogo(
                        proximo,
                        f"IT{proximo:05d}",
                        f"{descricao}{v}",
                        categoria_id,
                        rng.choice(forn_cat).id if forn_cat and not servico else None,
                        um,
                        vl_ref,
                        round(vl_ref * cv, 2),
                        True,
                        categoria_id in (1, 7),
                        datetime(2021, 1, 4, 9, 0)
                        + timedelta(days=rng.choice([0, 0, 0, 90, 365, 730])),
                    )
                )
                proximo += 1
    return itens


def construir_mundo() -> Mundo:
    rng = random.Random(f"{SEMENTE}-mundo")
    usuarios = _usuarios(rng)
    parceiros = _parceiros(rng, usuarios)
    fornecedores = _fornecedores(rng)
    itens = _itens(rng, fornecedores)
    return Mundo(usuarios, parceiros, fornecedores, itens)
