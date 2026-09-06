"""Configuração 12-factor: tudo vem do ambiente (.env local, nunca versionado)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# A raiz do projeto, derivada do próprio pacote (src/interiores_fictoria/ → 2 níveis
# acima). É o que torna caminhos relativos independentes do diretório de quem chama:
# um notebook em notebooks/ e um script na raiz enxergam o MESMO lake e o MESMO .env.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def _carregar_env() -> None:
    load_dotenv(RAIZ_PROJETO / ".env")


def _driver() -> str:
    return os.environ.get("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")


def _conexao_odbc(host: str, porta: str, banco: str, usuario: str, senha: str) -> str:
    """String de conexão ODBC para um SQL Server em container (sem certificado válido).

    `TrustServerCertificate=yes` é aceitável no laboratório, jamais em produção.
    """
    return (
        f"Driver={{{_driver()}}};Server=tcp:{host},{porta};Database={banco};"
        f"Uid={usuario};Pwd={senha};Encrypt=yes;TrustServerCertificate=yes"
    )


def _senha_origem() -> str:
    _carregar_env()
    senha = os.environ.get("MSSQL_SA_PASSWORD")
    if not senha:
        raise RuntimeError("MSSQL_SA_PASSWORD ausente: copie .env.example para .env e preencha.")
    return senha


def conexao_origem() -> str:
    """Conexão ODBC do sistema comercial simulado (`db_fictoria`), das variáveis MSSQL_*."""
    return _conexao_odbc(
        os.environ.get("MSSQL_HOST", "localhost"),
        os.environ.get("MSSQL_PORT", "1433"),
        os.environ.get("ORIGEM_DB", "db_fictoria"),
        os.environ.get("MSSQL_USER", "sa"),
        _senha_origem(),
    )


def conexao_staging() -> str:
    """Conexão ODBC do staging (`stg_fictoria`), no mesmo servidor do sistema comercial."""
    return _conexao_odbc(
        os.environ.get("MSSQL_HOST", "localhost"),
        os.environ.get("MSSQL_PORT", "1433"),
        os.environ.get("STAGING_DB", "stg_fictoria"),
        os.environ.get("MSSQL_USER", "sa"),
        _senha_origem(),
    )


def conexao_warehouse() -> str:
    """Conexão ODBC do warehouse multidimensional.

    Duas formas, ambas 12-factor: `DW_URL` (string ODBC completa, como a que um Azure SQL
    entrega) tem precedência; sem ela, a string é montada das partes DW_HOST/PORT/DB/USER/
    DW_SA_PASSWORD (o container local).
    """
    _carregar_env()
    url = os.environ.get("DW_URL", "").strip()
    if url:
        return url
    senha = os.environ.get("DW_SA_PASSWORD")
    if not senha:
        raise RuntimeError("DW_SA_PASSWORD ausente: defina no .env (ver .env.example).")
    return _conexao_odbc(
        os.environ.get("DW_HOST", "localhost"),
        os.environ.get("DW_PORT", "1434"),
        os.environ.get("DW_DB", "dw_fictoria"),
        os.environ.get("DW_USER", "sa"),
        senha,
    )


def anos_carga_dw() -> list[int] | None:
    """Partições a carregar no warehouse (DW_ANOS='2024,2025'); None = todas."""
    _carregar_env()
    bruto = os.environ.get("DW_ANOS", "").strip()
    return [int(a) for a in bruto.split(",") if a.strip()] or None


def url_lake() -> str:
    """Onde o lake vive, em URL fsspec: `file://...` local ou `s3://...` (12-factor).

    O padrão é o diretório `data/lake` do projeto (gitignorado). Trocar de storage é
    trocar UMA variável de ambiente, nunca o código. Caminho local RELATIVO é ancorado
    na raiz do projeto, para funcionar igual num script na raiz e num notebook em
    `notebooks/` (o cwd de quem chama não importa).
    """
    _carregar_env()
    url = os.environ.get("LAKE_URL", "data/lake")
    if "://" not in url and not Path(url).is_absolute():
        return str(RAIZ_PROJETO / url)
    return url
