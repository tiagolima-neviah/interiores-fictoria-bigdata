"""Orquestração leve: roda o pipeline inteiro, em ordem, parando na primeira falha.

Uso: `uv run pipeline` (staging → bronze → silver → gold → régua da gold → warehouse) ou
`uv run pipeline --completo` para incluir a origem (gerador + régua) e os notebooks.
Cada etapa é o mesmo comando que roda sozinho; aqui só se encadeiam, com tempo por etapa.
Um agendador (cron, Task Scheduler, GitHub Actions) chama isto uma vez por dia.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

from interiores_fictoria.bronze.extrator import main as bronze
from interiores_fictoria.gold.construtor import main as gold
from interiores_fictoria.silver.transformador import main as silver
from interiores_fictoria.staging.carga_incremental import main as carga_staging
from interiores_fictoria.validacao.regua_gold import main as regua_gold
from interiores_fictoria.warehouse.carga import main as carga_dw

Etapa = tuple[str, Callable[[], None]]

DIARIO: list[Etapa] = [
    ("carga-staging", carga_staging),
    ("bronze-staging", bronze),
    ("silver-staging", silver),
    ("gold-staging", gold),
    ("regua-gold", regua_gold),
    ("carga-dw", carga_dw),
]


def _completo() -> list[Etapa]:
    from interiores_fictoria.gerador.principal import main as gerador
    from interiores_fictoria.notebooks.construtor import main as nb_qualidade
    from interiores_fictoria.notebooks.modelo import main as nb_modelo
    from interiores_fictoria.validacao.regua import main as regua_origem

    return [
        ("gerador-origem", gerador),
        ("regua-origem", regua_origem),
        *DIARIO,
        ("notebooks-qualidade", nb_qualidade),
        ("notebooks-modelo", nb_modelo),
    ]


def main() -> None:
    p = argparse.ArgumentParser(
        description="Pipeline Fictoria: staging → bronze → silver → gold → warehouse."
    )
    p.add_argument(
        "--completo", action="store_true", help="inclui gerador, régua da origem e notebooks"
    )
    args = p.parse_args()
    etapas = _completo() if args.completo else DIARIO
    inicio = time.perf_counter()
    tempos: list[tuple[str, float]] = []
    argv = sys.argv
    for nome, funcao in etapas:
        print(f"\n{'=' * 78}\n>> {nome}\n{'=' * 78}")
        t0 = time.perf_counter()
        sys.argv = [nome]  # cada etapa tem o seu argparse; não herda os argumentos do pipeline
        try:
            funcao()
        except SystemExit as e:
            if e.code not in (None, 0):
                print(f"\nPipeline interrompido em {nome} (saída {e.code}).")
                raise
        finally:
            sys.argv = argv
        tempos.append((nome, time.perf_counter() - t0))
    print(f"\n{'=' * 78}\nPipeline concluído em {time.perf_counter() - inicio:.1f}s\n")
    for nome, t in tempos:
        print(f"  {nome:22} {t:>7.1f}s")


if __name__ == "__main__":
    main()
