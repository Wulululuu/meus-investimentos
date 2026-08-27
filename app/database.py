"""Acesso ao banco de dados.

Usa a biblioteca `libsql` (compativel com o dialeto SQLite) em vez do
`sqlite3` da biblioteca padrao, porque o mesmo codigo passa a rodar tanto
localmente (arquivo .db) quanto contra um banco Turso remoto (usado quando
o app esta hospedado, para desktop e celular compartilharem os mesmos
dados). Qual dos dois usar e' decidido sozinho, via variaveis de ambiente:

- Se TURSO_DATABASE_URL estiver definida -> conecta no banco remoto (Turso).
- Caso contrario -> usa um arquivo local `investimentos.db` (util para
  rodar/testar o backend na sua propria maquina, sem depender de internet).

O `libsql` retorna cada linha como uma tupla simples (sem suportar
`linha["coluna"]` como o sqlite3.Row). As classes _LinhaCompat/_CursorCompat/
_ConexaoCompat abaixo recriam esse comportamento por cima do libsql, para
que o resto do app (main.py, updater.py, patrimonio.py, exportador.py)
continue usando `linha["coluna"]` sem precisar mudar uma linha sequer.
"""
from __future__ import annotations

import os
from pathlib import Path

import libsql

DB_PATH = Path(__file__).resolve().parent.parent / "investimentos.db"

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS investimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    tipo TEXT NOT NULL,
    quantidade REAL NOT NULL,
    preco_medio_compra REAL NOT NULL,
    data_compra TEXT NOT NULL,
    criado_em TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cotacoes_atuais (
    ticker TEXT PRIMARY KEY,
    nome_curto TEXT,
    preco_atual REAL,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS historico_precos (
    ticker TEXT,
    data TEXT,
    fechamento REAL,
    PRIMARY KEY (ticker, data)
);

CREATE TABLE IF NOT EXISTS proventos_recebidos (
    ticker TEXT,
    data_ex TEXT,
    valor_por_cota REAL,
    PRIMARY KEY (ticker, data_ex)
);

CREATE TABLE IF NOT EXISTS proventos_futuros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    data_com TEXT,
    data_pagamento TEXT,
    valor_por_cota REAL,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    quantidade REAL NOT NULL,
    preco_unitario REAL NOT NULL,
    data_venda TEXT NOT NULL,
    criado_em TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    senha_sal TEXT NOT NULL,
    criado_em TEXT DEFAULT (datetime('now'))
);
"""


class _LinhaCompat:
    """Imita sqlite3.Row: acesso por nome (linha['col']) ou índice (linha[0])."""

    __slots__ = ("_colunas", "_valores")

    def __init__(self, colunas: list[str], valores: tuple):
        self._colunas = colunas
        self._valores = valores

    def __getitem__(self, chave):
        if isinstance(chave, str):
            return self._valores[self._colunas.index(chave)]
        return self._valores[chave]

    def keys(self):
        return list(self._colunas)

    def __iter__(self):
        return iter(self._valores)

    def __len__(self):
        return len(self._valores)

    def __repr__(self):
        return f"<Linha {dict(zip(self._colunas, self._valores))}>"


class _CursorCompat:
    def __init__(self, cursor_bruto):
        self._cursor = cursor_bruto
        desc = cursor_bruto.description
        self._colunas = [d[0] for d in desc] if desc else []

    def fetchall(self) -> list[_LinhaCompat]:
        return [_LinhaCompat(self._colunas, row) for row in self._cursor.fetchall()]

    def fetchone(self) -> _LinhaCompat | None:
        row = self._cursor.fetchone()
        return _LinhaCompat(self._colunas, row) if row is not None else None

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def __iter__(self):
        return iter(self.fetchall())


class _ConexaoCompat:
    def __init__(self, conexao_bruta):
        self._conn = conexao_bruta

    def execute(self, sql: str, parametros: tuple = ()) -> _CursorCompat:
        return _CursorCompat(self._conn.execute(sql, parametros))

    def executemany(self, sql: str, sequencia_parametros) -> None:
        self._conn.executemany(sql, list(sequencia_parametros))

    def executescript(self, script: str) -> None:
        self._conn.executescript(script)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def get_conn() -> _ConexaoCompat:
    if TURSO_DATABASE_URL:
        conexao_bruta = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    else:
        conexao_bruta = libsql.connect(str(DB_PATH))
    conn = _ConexaoCompat(conexao_bruta)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrar(conn: _ConexaoCompat) -> None:
    """Ajustes de schema em bancos já existentes (evita ter que apagar dados)."""
    conn.execute("DROP TABLE IF EXISTS sugestoes")
    conn.execute("DROP TABLE IF EXISTS perfil_investidor")
    conn.execute("DROP TABLE IF EXISTS sugestoes_ia")
    conn.execute("DELETE FROM meta WHERE chave = 'sugestoes_ia_gerado_em'")


def init_db():
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        _migrar(conn)
        conn.commit()
    finally:
        conn.close()
