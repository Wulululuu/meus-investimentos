"""Autenticação simples de usuário+senha (um único usuário, já que o app é
pessoal). Senha nunca é guardada em texto puro: usamos scrypt (embutido no
Python, sem dependência extra) para gerar um hash com sal aleatório.

O login "abre a porteira" de todas as rotas de API (menos /api/auth/*) via
uma sessão de cookie assinada (SessionMiddleware do Starlette) — funciona
tanto no navegador do celular quanto na janela desktop (que também é, por
baixo dos panos, um navegador embutido)."""
from __future__ import annotations

import hashlib
import os

from .database import get_conn


def _gerar_hash(senha: str, sal: bytes) -> str:
    derivado = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=2**14, r=8, p=1)
    return derivado.hex()


def existe_usuario() -> bool:
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS total FROM usuarios").fetchone()
        return row["total"] > 0
    finally:
        conn.close()


def criar_usuario(username: str, senha: str) -> None:
    sal = os.urandom(16)
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, senha_hash, senha_sal) VALUES (?, ?, ?)",
            (username, _gerar_hash(senha, sal), sal.hex()),
        )
        conn.commit()
    finally:
        conn.close()


def verificar_login(username: str, senha: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT senha_hash, senha_sal FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return False
    sal = bytes.fromhex(row["senha_sal"])
    return _gerar_hash(senha, sal) == row["senha_hash"]
