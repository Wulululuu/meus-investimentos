"""Carrega config.env (se existir) para variáveis de ambiente, ANTES de
qualquer outro import do app — importante porque app/database.py decide
local-vs-Turso lendo os.environ assim que é importado."""
from __future__ import annotations

import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.env"


def carregar() -> None:
    if not CONFIG_PATH.exists():
        return
    for linha in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip()
        if valor and chave not in os.environ:
            os.environ[chave] = valor
