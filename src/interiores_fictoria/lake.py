"""O lake: bronze, silver e gold em parquet, com storage plugável via fsspec.

`LAKE_URL` decide onde tudo vive (`data/lake` local por padrão; `s3://bucket/prefixo` na
nuvem). Este módulo concentra os caminhos, a escrita/leitura de parquet e os manifestos
de linhagem, para as camadas não conhecerem detalhes de storage.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import fsspec
import pyarrow as pa
import pyarrow.parquet as pq

from interiores_fictoria.config import url_lake


@dataclass(frozen=True)
class Lake:
    fs: Any
    raiz: str

    def caminho(self, *partes: str) -> str:
        return "/".join([self.raiz.rstrip("/"), *[p.strip("/") for p in partes]])

    def existe(self, *partes: str) -> bool:
        return bool(self.fs.exists(self.caminho(*partes)))

    def listar(self, *partes: str) -> list[str]:
        alvo = self.caminho(*partes)
        if not self.fs.exists(alvo):
            return []
        return sorted(str(p) for p in self.fs.ls(alvo, detail=False))

    def escrever_parquet(self, tabela: pa.Table, *partes: str) -> str:
        destino = self.caminho(*partes)
        self.fs.makedirs(destino.rsplit("/", 1)[0], exist_ok=True)
        with self.fs.open(destino, "wb") as f:
            pq.write_table(tabela, f, compression="zstd")
        return destino

    def ler_parquet(self, *partes: str) -> pa.Table:
        with self.fs.open(self.caminho(*partes), "rb") as f:
            return pq.read_table(f)

    def contar_parquet(self, *partes: str) -> int:
        with self.fs.open(self.caminho(*partes), "rb") as f:
            return int(pq.ParquetFile(f).metadata.num_rows)

    def escrever_json(self, dados: Any, *partes: str) -> str:
        destino = self.caminho(*partes)
        self.fs.makedirs(destino.rsplit("/", 1)[0], exist_ok=True)
        with self.fs.open(destino, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, default=str)
        return destino

    def ler_json(self, *partes: str) -> Any:
        if not self.existe(*partes):
            return None
        with self.fs.open(self.caminho(*partes), "r", encoding="utf-8") as f:
            return json.load(f)

    def apagar(self, *partes: str) -> None:
        alvo = self.caminho(*partes)
        if self.fs.exists(alvo):
            self.fs.rm(alvo, recursive=True)

    def glob_duckdb(self, *partes: str) -> str:
        """Padrão de leitura para o DuckDB (`read_parquet`), com o esquema da URL quando houver."""
        base = self.caminho(*partes)
        return base if "://" in base or base.startswith("/") else base


def abrir_lake(url: str | None = None) -> Lake:
    alvo = url or url_lake()
    fs, raiz = fsspec.core.url_to_fs(alvo)
    return Lake(fs, raiz)


@dataclass
class Manifesto:
    """Linhagem de uma execução: quem rodou o quê, quando, com quantas linhas."""

    camada: str
    execucao: str
    inicio: str
    fim: str = ""
    tabelas: dict[str, dict[str, Any]] | None = None

    def registrar(self, tabela: str, **dados: Any) -> None:
        if self.tabelas is None:
            self.tabelas = {}
        self.tabelas[tabela] = dados

    def fechar(self) -> dict[str, Any]:
        self.fim = datetime.now().isoformat(timespec="seconds")
        return asdict(self)


def novo_manifesto(camada: str) -> Manifesto:
    agora = datetime.now()
    return Manifesto(camada, agora.strftime("%Y%m%dT%H%M%S"), agora.isoformat(timespec="seconds"))
