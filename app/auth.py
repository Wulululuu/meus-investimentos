"""Autenticação de usuário+senha — cada usuário só vê os próprios
investimentos. Senha nunca é guardada em texto puro: usamos scrypt (embutido
no Python, sem dependência extra) para gerar um hash com sal aleatório.

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


def username_disponivel(username: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM usuarios WHERE username = ?", (username,)).fetchone()
        return row is None
    finally:
        conn.close()


def criar_usuario(username: str, senha: str) -> int:
    """Cria o usuário e retorna seu id. Se for o PRIMEIRO usuário do sistema,
    ele "herda" automaticamente qualquer investimento/venda órfã (dados de
    antes de existir login multiusuário, ou migrados de uma versão anterior
    do app) — assim ninguém perde a carteira que já tinha cadastrado."""
    era_o_primeiro = not existe_usuario()
    sal = os.urandom(16)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO usuarios (username, senha_hash, senha_sal) VALUES (?, ?, ?)",
            (username, _gerar_hash(senha, sal), sal.hex()),
        )
        novo_id = cur.lastrowid

        if era_o_primeiro:
            conn.execute("UPDATE investimentos SET usuario_id = ? WHERE usuario_id IS NULL", (novo_id,))
            conn.execute("UPDATE vendas SET usuario_id = ? WHERE usuario_id IS NULL", (novo_id,))

        conn.commit()
        return novo_id
    finally:
        conn.close()


def obter_usuario_id(username: str, senha: str) -> int | None:
    """Verifica a senha e, se correta, retorna o id do usuário (ou None)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, senha_hash, senha_sal FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    sal = bytes.fromhex(row["senha_sal"])
    if _gerar_hash(senha, sal) != row["senha_hash"]:
        return None
    return row["id"]
