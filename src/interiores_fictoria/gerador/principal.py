"""Entrada do gerador: materializa o sistema comercial simulado como de uma data T.

Uso:
    uv run gerador-origem                       # T = data corrente do universo (04/09/2026 18h)
    uv run gerador-origem --ate 2026-09-09T12:54  # avança o relógio: só o delta é aplicado
    uv run gerador-origem --agora               # T = relógio real da máquina

Idempotente por construção: o estado desejado é sincronizado por MERGE, então rodar de
novo com a mesma T não altera nenhuma linha (e nenhum rowversion). Rodar com T maior
insere e atualiza apenas o que aconteceu entre as duas datas.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

from interiores_fictoria import db
from interiores_fictoria.config import conexao_origem
from interiores_fictoria.gerador import DATA_CORRENTE, HORIZONTE
from interiores_fictoria.gerador.materializar import TABELAS
from interiores_fictoria.gerador.mundo import construir_mundo
from interiores_fictoria.gerador.planejador import planejar_universo


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Gerador determinístico da origem Fictoria (db_fictoria)."
    )
    p.add_argument(
        "--ate",
        help="instante T (ISO 8601, ex.: 2026-09-09T12:54); padrão: data corrente do universo",
    )
    p.add_argument("--agora", action="store_true", help="usa o relógio real da máquina como T")
    p.add_argument(
        "--so-planejar", action="store_true", help="planeja e imprime contagens, sem tocar o banco"
    )
    p.add_argument(
        "--recriar",
        action="store_true",
        help="apaga todas as linhas da origem antes de materializar (quando o plano/semente mudar)",
    )
    return p.parse_args()


def _instante(args: argparse.Namespace) -> datetime:
    if args.agora:
        return datetime.now().replace(microsecond=0)
    if args.ate:
        return datetime.fromisoformat(args.ate)
    return DATA_CORRENTE


def main() -> None:
    args = _argumentos()
    t = _instante(args)
    if t > HORIZONTE:
        raise SystemExit(f"T além do horizonte planejado ({HORIZONTE:%Y-%m-%d}); ajuste HORIZONTE.")
    inicio = time.perf_counter()
    print("Planejando o universo (semente fixa) ... ", end="", flush=True)
    universo = planejar_universo(construir_mundo())
    n_venda = sum(1 for o in universo.orcamentos if o.tipo_id == 1)
    print(
        f"{len(universo.orcamentos)} orçamentos planejados ({n_venda} de venda), "
        f"{len(universo.clientes)} clientes, em {time.perf_counter() - inicio:.1f}s"
    )
    print(f"Materializando como de {t:%Y-%m-%d %H:%M}\n")
    print(f"  {'tabela':34} {'linhas':>9} {'inseridas':>10} {'atualizadas':>12} {'tempo':>7}")
    conn = None if args.so_planejar else db.conectar(conexao_origem())
    total_ins = total_upd = 0
    try:
        if conn is not None and args.recriar:
            print("  (--recriar) apagando as linhas da origem, filhos antes dos pais ...")
            for construtor in reversed(TABELAS):
                db.executar(conn, f"DELETE FROM {construtor(universo, HORIZONTE).nome}")
            conn.commit()
        for construtor in TABELAS:
            t0 = time.perf_counter()
            tabela = construtor(universo, t)
            if conn is None:
                print(f"  {tabela.nome:34} {len(tabela.linhas):>9}")
                continue
            r = db.sincronizar(
                conn,
                tabela.nome,
                tabela.colunas,
                tabela.linhas,
                identidade=tabela.identidade,
                colunas_extra_update={"dt_atualizacao": "SYSDATETIME()"},
            )
            total_ins += r.inseridas
            total_upd += r.atualizadas
            print(
                f"  {tabela.nome:34} {r.recebidas:>9} {r.inseridas:>10} {r.atualizadas:>12} "
                f"{time.perf_counter() - t0:>6.1f}s"
            )
    finally:
        if conn is not None:
            conn.close()
    print(
        f"\nConcluído em {time.perf_counter() - inicio:.1f}s: {total_ins} linhas inseridas, "
        f"{total_upd} atualizadas."
    )
    if conn is not None:
        print("Valide com: uv run regua-origem")


if __name__ == "__main__":
    main()
