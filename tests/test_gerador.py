"""O gerador é determinístico e a materialização respeita o relógio."""

from datetime import datetime, timedelta

from interiores_fictoria.gerador import DATA_CORRENTE, materializar, mundo, planejador
from interiores_fictoria.gerador import parametros as P
from interiores_fictoria.validacao import bandas


def test_bandas_sao_intervalos_validos() -> None:
    for nome in dir(bandas):
        if nome.startswith("_") or nome == "Banda":
            continue
        valor = getattr(bandas, nome)
        if isinstance(valor, tuple) and len(valor) == 2:
            assert valor[0] <= valor[1], nome
        if isinstance(valor, dict):
            for ano, banda in valor.items():
                assert banda[0] <= banda[1], f"{nome} {ano}"


def test_mundo_e_deterministico() -> None:
    a, b = mundo.construir_mundo(), mundo.construir_mundo()
    assert [u.nome for u in a.usuarios] == [u.nome for u in b.usuarios]
    assert [p.cnpj for p in a.parceiros] == [p.cnpj for p in b.parceiros]
    assert len(a.vendedores()) == len(P.VENDEDORES)
    assert len(a.parceiros) == P.N_ESCRITORIOS + P.N_CONSTRUTORAS


def test_calendario_segue_sazonalidade_e_semente() -> None:
    jan, out = planejador._datas_cadastro(2024, 1), planejador._datas_cadastro(2024, 10)
    assert jan == planejador._datas_cadastro(2024, 1)
    assert len(out) > len(jan) * 1.3
    assert all(d.month == 1 for d in jan)
    assert all(P.HORA_INICIO <= d.hour < P.HORA_FIM for d in jan)


def test_cabecalho_e_detalhe_sao_deterministicos() -> None:
    m = mundo.construir_mundo()
    dt = datetime(2024, 5, 7, 10, 30)
    c1, c2 = planejador._cabecalho(m, 42, dt), planejador._cabecalho(m, 42, dt)
    assert (c1.canal, c1.vendedor.id, c1.vl_bruto_alvo) == (
        c2.canal,
        c2.vendedor.id,
        c2.vl_bruto_alvo,
    )
    assert c1.u_desfecho == c2.u_desfecho
    o1 = planejador.Planejador(m)._detalhar(c1, 0.5)
    o2 = planejador.Planejador(m)._detalhar(c2, 0.5)
    assert [i.vl_total for i in o1.itens] == [i.vl_total for i in o2.itens]
    soma = round(sum(i.vl_total for i in o1.itens if i.dt_cancelou is None), 2)
    assert o1.vl_bruto == soma or o1.dt_cadastro.year <= 2022
    assert o1.fases[0].dt_entrada == dt
    for anterior, seguinte in zip(o1.fases, o1.fases[1:], strict=False):
        assert anterior.dt_saida == seguinte.dt_entrada


def test_materializacao_respeita_o_relogio() -> None:
    m = mundo.construir_mundo()
    pl = planejador.Planejador(m)
    dt = datetime(2023, 8, 1, 11, 0)
    orc = pl._detalhar(planejador._cabecalho(m, 7, dt), 0.99)  # ganho quase certo
    universo = planejador.Universo(m, pl.clientes, [orc])
    cedo = materializar.t_orcamento_fase_hist(universo, dt + timedelta(hours=1))
    tarde = materializar.t_orcamento_fase_hist(universo, DATA_CORRENTE)
    assert len(cedo.linhas) <= len(tarde.linhas)
    abertas_cedo = [linha for linha in cedo.linhas if linha[4] is None]
    assert len(abertas_cedo) == 1  # exatamente uma fase em aberto no instante T
    antes = materializar.t_orcamento(universo, dt - timedelta(days=1))
    assert antes.linhas == []
    depois = materializar.t_orcamento(universo, DATA_CORRENTE)
    assert len(depois.linhas) == 1
    assert depois.colunas[6] == "fase_id"
