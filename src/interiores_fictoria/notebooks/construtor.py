"""Gera e EXECUTA os notebooks de auditoria de qualidade do bronze.

Uso: `uv run notebooks-qualidade`. O construtor mede cada achado no bronze, escreve o
notebook (célula de evidência + Nota Técnica com o observado) e o executa com o nbclient,
gravando as saídas. Assim a nota nunca antecipa a célula: os números da nota são os mesmos
que a célula imprime, medidos na mesma execução. Sem caminho absoluto: o notebook resolve
o lake pela configuração do pacote.
"""

from __future__ import annotations

import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from interiores_fictoria import duck
from interiores_fictoria.config import RAIZ_PROJETO
from interiores_fictoria.qualidade import achados as A

CADERNOS = {
    1: (
        "01_qualidade_cadastro_funil",
        "Auditoria de qualidade do bronze: cadastro e funil comercial",
    ),
    2: ("02_qualidade_financeiro_obra", "Auditoria de qualidade do bronze: financeiro e obra"),
}

SETUP = """import duckdb, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from interiores_fictoria import duck

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 160)
con, lake = duck.conectar()
print("lake:", lake.raiz)
print("cargas no bronze:", len(lake.listar("bronze", "_controle", "cargas")))
"""

GRAFICO = '''df = con.execute("""{sql}""").df()
fig, ax = plt.subplots(figsize=(9, max(3, 0.32 * len(df))))
ax.barh(df.iloc[:, 0].astype(str), df.iloc[:, 1], color="#8c6d46")
ax.invert_yaxis()
ax.set_title({titulo!r})
ax.set_xlabel({eixo!r})
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
plt.tight_layout()
plt.show()
'''

RETRATO = '''# Retrato do funil: volumes, conversão e carteira por ano (o cenário que os achados afetam)
df = con.execute("""
SELECT YEAR(o.dt_cadastro) AS ano, COUNT(*) AS orcamentos,
       SUM(CASE WHEN f.grupo = 'GANHO' THEN 1 ELSE 0 END) AS ganhos,
       SUM(CASE WHEN f.grupo = 'PERDIDO' THEN 1 ELSE 0 END) AS perdidos,
       SUM(CASE WHEN f.grupo = 'ABERTO' THEN 1 ELSE 0 END) AS abertos,
       ROUND(SUM(CASE WHEN f.grupo = 'GANHO' THEN 1.0 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN f.grupo IN ('GANHO','PERDIDO') THEN 1.0 ELSE 0 END), 0), 3)
           AS conversao_sobre_fechados,
       ROUND(SUM(o.vl_total_liquido) / 1e6, 1) AS liquido_mi
FROM b_orcamento o JOIN b_fase f ON f.id = o.fase_id
WHERE o.tipo_orcamento_id = 1 AND o.dt_cancelou IS NULL
GROUP BY 1 ORDER BY 1
""").df()
display(df)
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.bar(df["ano"].astype(str), df["orcamentos"], color="#c9b79c", label="orçamentos")
ax2 = ax.twinx()
ax2.plot(df["ano"].astype(str), df["conversao_sobre_fechados"] * 100, color="#5b4a2f", marker="o",
         label="conversão sobre fechados (%)")
ax.set_title("Orçamentos por ano e o arco da conversão")
ax2.set_ylim(0, 60)
for spine in ("top",):
    ax.spines[spine].set_visible(False); ax2.spines[spine].set_visible(False)
plt.tight_layout()
plt.show()
'''


def _nota(achado: A.Achado, observado: str) -> str:
    return (
        f"**Nota Técnica {achado.id}**\n\n"
        f"- **Observado:** {observado}.\n"
        f"- **Por que importa:** {achado.por_que_importa}\n"
        f"- **Ação (regra da silver):** {achado.regra_silver}"
    )


def _observado(achado: A.Achado, texto: str) -> str:
    if achado.formato == "pct":
        return f"taxa observada de {texto} na base analisada (métrica: `{achado.id}`)"
    return f"{texto} ocorrências na base analisada (métrica: `{achado.id}`)"


def construir_caderno(
    caderno: int, medidas: dict[str, dict[str, str | float]]
) -> nbformat.NotebookNode:
    nome, titulo = CADERNOS[caderno]
    nb = new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.cells.append(
        new_markdown_cell(
            f"# {titulo}\n\n"
            "Notebook de auditoria da **Fictoria Casa & Interiores** (empresa fictícia, dados 100% "
            "sintéticos). Lê o **bronze** (estado corrente por chave) com DuckDB e evidencia, achado a "
            "achado, a sujeira que a **silver** precisa tratar. Cada seção termina numa **Nota Técnica** "
            "(Observado · Por que importa · Ação) escrita a partir do que a célula mostrou; o conjunto "
            "das ações é o [catálogo de achados](../docs/08_catalogo_achados_silver.md), o contrato da "
            "silver.\n\n"
            "> Reprodutível: `uv run notebooks-qualidade` reconstrói e reexecuta este notebook a partir "
            "de `src/interiores_fictoria/qualidade/achados.py`."
        )
    )
    nb.cells.append(new_code_cell(SETUP))
    if caderno == 1:
        nb.cells.append(
            new_markdown_cell(
                "## 0. Retrato do funil\n\nAntes dos defeitos, o cenário: "
                "volumes, desfechos e o arco da conversão por ano."
            )
        )
        nb.cells.append(new_code_cell(RETRATO))
    for k, achado in enumerate(A.por_caderno(caderno), start=1):
        nb.cells.append(new_markdown_cell(f"## {k}. {achado.id} · {achado.titulo}"))
        nb.cells.append(
            new_code_cell(
                f'df = con.execute("""{achado.sql}""").df()\ndisplay(df)\n'
                f'metrica = con.execute("""{achado.metrica_sql}""").fetchone()[0]\n'
                f'print("métrica {achado.id}:", metrica)'
            )
        )
        if achado.grafico:
            nb.cells.append(
                new_code_cell(
                    GRAFICO.format(
                        sql=achado.grafico, titulo=achado.titulo, eixo="taxa sem follow-up"
                    )
                )
            )
        nb.cells.append(
            new_markdown_cell(_nota(achado, _observado(achado, str(medidas[achado.id]["texto"]))))
        )
    nb.cells.append(
        new_markdown_cell(
            "## Encerramento\n\nOs achados acima entram no catálogo com id, regra e taxa observada. "
            "A silver implementa as regras e presta contas: para cada achado, quantas linhas foram "
            "afetadas, com o veredito que reprova a si mesmo quando a contagem não bate."
        )
    )
    return nb


def executar(nb: nbformat.NotebookNode, destino: Path) -> None:
    cliente = NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(destino.parent)}},
    )
    cliente.execute()
    nbformat.write(nb, destino)


def main() -> None:
    inicio = time.perf_counter()
    con, _lake = duck.conectar()
    medidas = A.medir_todos(con)
    con.close()
    pasta = RAIZ_PROJETO / "notebooks"
    pasta.mkdir(exist_ok=True)
    print("Achados medidos no bronze:")
    for aid, m in medidas.items():
        print(f"  {aid}  {str(m['texto']):>12}  {m['titulo']}")
    for caderno, (nome, _) in CADERNOS.items():
        t0 = time.perf_counter()
        nb = construir_caderno(caderno, medidas)
        destino = pasta / f"{nome}.ipynb"
        executar(nb, destino)
        print(f"\n{destino.relative_to(RAIZ_PROJETO)} executado em {time.perf_counter() - t0:.1f}s")
    print(f"\nConcluído em {time.perf_counter() - inicio:.1f}s. Próximo: uv run silver-staging")


if __name__ == "__main__":
    main()
