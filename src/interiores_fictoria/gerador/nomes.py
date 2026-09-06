"""Geradores de nomes, documentos e endereços sintéticos (nada aqui é real)."""

from __future__ import annotations

import random

PRIMEIROS_NOMES = [
    "Ana",
    "Beatriz",
    "Camila",
    "Carolina",
    "Fernanda",
    "Gabriela",
    "Helena",
    "Isabela",
    "Juliana",
    "Larissa",
    "Letícia",
    "Luiza",
    "Mariana",
    "Marina",
    "Natália",
    "Patrícia",
    "Paula",
    "Rafaela",
    "Renata",
    "Sofia",
    "Tatiana",
    "Vanessa",
    "Vitória",
    "Bruna",
    "Clara",
    "André",
    "Bruno",
    "Carlos",
    "Daniel",
    "Diego",
    "Eduardo",
    "Felipe",
    "Fernando",
    "Gustavo",
    "Henrique",
    "João",
    "Leonardo",
    "Lucas",
    "Marcelo",
    "Mateus",
    "Paulo",
    "Pedro",
    "Rafael",
    "Ricardo",
    "Rodrigo",
    "Thiago",
    "Vinícius",
    "Alexandre",
    "Caio",
    "Otávio",
    "Renato",
]
SOBRENOMES = [
    "Almeida",
    "Andrade",
    "Araújo",
    "Barbosa",
    "Barros",
    "Batista",
    "Cardoso",
    "Carvalho",
    "Castro",
    "Costa",
    "Cunha",
    "Dias",
    "Duarte",
    "Fernandes",
    "Ferreira",
    "Fonseca",
    "Freitas",
    "Garcia",
    "Gomes",
    "Gonçalves",
    "Lima",
    "Lopes",
    "Machado",
    "Martins",
    "Melo",
    "Mendes",
    "Miranda",
    "Monteiro",
    "Moraes",
    "Moreira",
    "Moura",
    "Nascimento",
    "Nogueira",
    "Nunes",
    "Oliveira",
    "Pereira",
    "Pinto",
    "Ramos",
    "Reis",
    "Ribeiro",
    "Rocha",
    "Rodrigues",
    "Santos",
    "Silva",
    "Soares",
    "Souza",
    "Teixeira",
    "Vieira",
    "Xavier",
    "Azevedo",
    "Bittencourt",
    "Cavalcanti",
    "Guimarães",
    "Leal",
    "Sampaio",
    "Toledo",
    "Vasconcelos",
    "Prado",
    "Tavares",
]
BAIRROS_SP = [
    # (bairro, peso)
    ("Jardim Europa", 10),
    ("Jardim América", 10),
    ("Jardim Paulista", 9),
    ("Jardim Paulistano", 6),
    ("Cidade Jardim", 7),
    ("Itaim Bibi", 9),
    ("Vila Nova Conceição", 7),
    ("Alto de Pinheiros", 8),
    ("Morumbi", 6),
    ("Pacaembu", 4),
    ("Higienópolis", 6),
    ("Brooklin", 4),
    ("Moema", 5),
    ("Vila Olímpia", 3),
    ("Pinheiros", 4),
    ("Campo Belo", 3),
    ("Chácara Flora", 2),
    ("Panamby", 2),
    ("Real Parque", 2),
    ("Jardim Guedala", 3),
]
LITORAL_CAMPO = [
    ("Guarujá", "SP", "LITORAL"),
    ("Riviera de São Lourenço", "SP", "LITORAL"),
    ("Ilhabela", "SP", "LITORAL"),
    ("Ubatuba", "SP", "LITORAL"),
    ("Itu", "SP", "CAMPO"),
    ("Bragança Paulista", "SP", "CAMPO"),
    ("Atibaia", "SP", "CAMPO"),
    ("Campos do Jordão", "SP", "CAMPO"),
    ("Indaiatuba", "SP", "CAMPO"),
]
LOGRADOUROS = [
    "Rua das Magnólias",
    "Alameda dos Jacarandás",
    "Rua Ipê Amarelo",
    "Avenida das Palmeiras",
    "Rua Flamboyant",
    "Rua dos Manacás",
    "Alameda das Acácias",
    "Rua Quaresmeira",
    "Rua das Sibipirunas",
    "Praça dos Pinheiros",
    "Rua das Tipuanas",
    "Alameda Paineira",
    "Rua Cerejeira",
    "Rua das Orquídeas",
    "Avenida dos Ipês",
    "Rua Jequitibá",
]
PALAVRAS_ESCRITORIO = [
    "Studio",
    "Atelier",
    "Casa",
    "Traço",
    "Linha",
    "Volume",
    "Escala",
    "Planta",
    "Forma",
    "Luz",
    "Espaço",
    "Nó",
    "Vão",
    "Ponto",
    "Eixo",
    "Plano",
]
PALAVRAS_CONSTRUTORA = [
    "Engenharia",
    "Construções",
    "Incorporadora",
    "Obras",
    "Empreendimentos",
    "Construtora",
]
DOMINIOS = ["exemplo.com.br", "email.com.br", "correio.com", "mail.com.br"]


def nome_pessoa(rng: random.Random) -> str:
    return f"{rng.choice(PRIMEIROS_NOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"


def nome_curto(rng: random.Random) -> str:
    return f"{rng.choice(PRIMEIROS_NOMES)} {rng.choice(SOBRENOMES)}"


def login(nome: str, sufixo: int) -> str:
    partes = nome.lower().split()
    base = f"{partes[0]}.{partes[-1]}"
    base = (
        base.replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return f"{base}{sufixo}"


def email(nome: str, rng: random.Random) -> str:
    return f"{login(nome, rng.randint(1, 99))}@{rng.choice(DOMINIOS)}"


def telefone(rng: random.Random) -> str:
    return f"11 9{rng.randint(6000, 9999)}-{rng.randint(1000, 9999)}"


def _dv_cpf(digitos: list[int]) -> int:
    peso = len(digitos) + 1
    soma = sum(d * (peso - i) for i, d in enumerate(digitos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cpf(rng: random.Random) -> str:
    """CPF sintético com dígitos verificadores válidos (não pertence a ninguém)."""
    base = [rng.randint(0, 9) for _ in range(9)]
    d1 = _dv_cpf(base)
    d2 = _dv_cpf(base + [d1])
    return "".join(map(str, base + [d1, d2]))


def _dv_cnpj(digitos: list[int]) -> int:
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(digitos) :]
    soma = sum(d * p for d, p in zip(digitos, pesos, strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj(rng: random.Random) -> str:
    base = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    d1 = _dv_cnpj(base)
    d2 = _dv_cnpj(base + [d1])
    return "".join(map(str, base + [d1, d2]))


def cep(rng: random.Random) -> str:
    return f"0{rng.randint(1000, 5999)}{rng.randint(0, 999):03d}"


def nome_escritorio(rng: random.Random) -> str:
    forma = rng.random()
    if forma < 0.35:
        return f"{rng.choice(SOBRENOMES)} Arquitetura"
    if forma < 0.55:
        return f"{rng.choice(PALAVRAS_ESCRITORIO)} {rng.choice(SOBRENOMES)}"
    if forma < 0.75:
        return f"{rng.choice(SOBRENOMES)} & {rng.choice(SOBRENOMES)} Arquitetos"
    if forma < 0.9:
        return f"{rng.choice(PALAVRAS_ESCRITORIO)} {rng.choice(PALAVRAS_ESCRITORIO)} Arquitetura"
    return f"{rng.choice(PRIMEIROS_NOMES)} {rng.choice(SOBRENOMES)} Interiores"


def nome_construtora(rng: random.Random) -> str:
    return f"{rng.choice(SOBRENOMES)} {rng.choice(PALAVRAS_CONSTRUTORA)}"


def bairro_sp(rng: random.Random) -> str:
    nomes = [b for b, _ in BAIRROS_SP]
    pesos = [p for _, p in BAIRROS_SP]
    return rng.choices(nomes, weights=pesos, k=1)[0]


def variar_grafia(nome: str, rng: random.Random) -> str:
    """Duplicidade por grafia: caixa alta, acento perdido ou espaço duplo (sujeira proposital)."""
    forma = rng.random()
    if forma < 0.4:
        return nome.upper()
    if forma < 0.7:
        return (
            nome.replace("á", "a")
            .replace("ã", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ç", "c")
        )
    return nome.replace(" ", "  ", 1)
