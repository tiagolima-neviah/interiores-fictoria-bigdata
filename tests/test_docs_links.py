"""Navegação da documentação: todo link relativo precisa apontar para algo que existe."""

import re
from pathlib import Path

import pytest

from interiores_fictoria import config

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVOS = [RAIZ / "README.md", *sorted((RAIZ / "docs").glob("*.md"))]


def _links_relativos(texto: str) -> list[str]:
    saida = []
    for alvo in re.findall(r"\]\(([^)]+)\)", texto):
        caminho = alvo.split("#")[0].strip()
        if not caminho or caminho.startswith(("http://", "https://", "mailto:")):
            continue
        saida.append(caminho)
    return saida


def test_todo_link_relativo_existe() -> None:
    quebrados = []
    for md in ARQUIVOS:
        for alvo in _links_relativos(md.read_text(encoding="utf-8")):
            if not (md.parent / alvo).resolve().exists():
                quebrados.append(f"{md.relative_to(RAIZ)} -> {alvo}")
    assert not quebrados, "links quebrados: " + "; ".join(quebrados)


def test_cadeia_de_navegacao_dos_docs() -> None:
    docs = sorted((RAIZ / "docs").glob("*.md"))
    for anterior, seguinte in zip(docs, docs[1:], strict=False):
        texto = anterior.read_text(encoding="utf-8")
        assert seguinte.name in texto, f"{anterior.name} não aponta para {seguinte.name}"
        assert "../README.md" in texto, f"{anterior.name} sem link Home"
    assert "../README.md" in docs[-1].read_text(encoding="utf-8")


def test_config_nunca_embute_credencial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem senha no ambiente, a configuração falha com mensagem clara (nada é hardcoded)."""
    monkeypatch.delenv("MSSQL_SA_PASSWORD", raising=False)
    monkeypatch.setattr(config, "_carregar_env", lambda: None)
    with pytest.raises(RuntimeError, match="MSSQL_SA_PASSWORD"):
        config.conexao_origem()


def test_config_monta_conexao_odbc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_carregar_env", lambda: None)
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "x")
    monkeypatch.setenv("MSSQL_PORT", "1499")
    conexao = config.conexao_staging()
    assert "Server=tcp:localhost,1499" in conexao
    assert "Database=stg_fictoria" in conexao
