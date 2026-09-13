"""Backup do banco de dados para a pasta backups/.

Antes, o backup era um `shutil.copy2` do arquivo `investimentos.db`. Isso
deixou de funcionar quando o app migrou para o Turso: o arquivo local
continua no disco, mas congelado no dia da migracao — os dados de verdade
passaram a viver no banco remoto. O backup seguia copiando o arquivo morto,
sem erro nenhum, dando a falsa impressao de que havia copia de seguranca.

Agora o backup le o banco que o app realmente usa (via `get_conn()`, que ja
decide local-vs-Turso sozinho) e escreve um arquivo .db SQLite de verdade.
O formato e o nome continuam iguais aos de antes
(`backups/investimentos_AAAA-MM-DD.db`), entao para restaurar basta copiar
o arquivo por cima de `investimentos.db` (ou importa-lo de volta no Turso).

Pode ser executado direto para testar/rodar sob demanda:

    python -m app.backup
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
import sqlite3
from pathlib import Path

import carregar_config

carregar_config.carregar()  # precisa rodar ANTES de importar .database (le os.environ no import)

from .database import DB_PATH, get_conn  # noqa: E402

BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUPS_PARA_MANTER = 14

log = logging.getLogger("backup")

# Tabelas internas do proprio SQLite, que nao devem (nem podem) ser recriadas.
_INTERNAS = ("sqlite_sequence", "sqlite_stat1")


def _e_turso() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL", "").strip())


def _objetos_do_schema(conn) -> list[tuple[str, str, str]]:
    """Retorna (tipo, nome, sql) de tabelas e indices definidos pelo usuario."""
    linhas = conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name"
    ).fetchall()
    return [(l["type"], l["name"], l["sql"]) for l in linhas]


def _colunas(conn, tabela: str) -> list[str]:
    linhas = conn.execute(f'PRAGMA table_info("{tabela}")').fetchall()
    return [l["name"] for l in linhas]


def dump_para_arquivo(destino: Path) -> int:
    """Le o banco em uso e escreve um SQLite novo em `destino`.

    Escreve primeiro num arquivo temporario e so renomeia no fim: se algo
    falhar no meio do caminho, nao fica um backup pela metade se passando
    por bom. Retorna o total de linhas copiadas.
    """
    temporario = destino.with_suffix(".db.parcial")
    temporario.unlink(missing_ok=True)

    origem = get_conn()
    try:
        objetos = _objetos_do_schema(origem)
        tabelas = [nome for tipo, nome, _ in objetos if tipo == "table" and nome not in _INTERNAS]

        saida = sqlite3.connect(temporario)
        try:
            for tipo, nome, sql in objetos:
                if nome in _INTERNAS:
                    continue
                saida.execute(sql)

            total = 0
            for tabela in tabelas:
                cols = _colunas(origem, tabela)
                if not cols:
                    continue
                linhas = origem.execute(f'SELECT * FROM "{tabela}"').fetchall()
                if not linhas:
                    continue
                lista_cols = ", ".join(f'"{c}"' for c in cols)
                marcadores = ", ".join("?" for _ in cols)
                saida.executemany(
                    f'INSERT INTO "{tabela}" ({lista_cols}) VALUES ({marcadores})',
                    [tuple(linha) for linha in linhas],
                )
                total += len(linhas)

            saida.commit()
        finally:
            saida.close()
    finally:
        origem.close()

    destino.unlink(missing_ok=True)
    temporario.replace(destino)
    return total


def _rotacionar() -> None:
    antigos = sorted(BACKUPS_DIR.glob("investimentos_*.db"))
    for arquivo in antigos[:-BACKUPS_PARA_MANTER]:
        arquivo.unlink(missing_ok=True)


def fazer_backup_banco() -> Path | None:
    """Gera o backup do dia em backups/ e apaga os mais antigos.

    Retorna o caminho gerado, ou None se nao foi possivel gerar (o app nunca
    deve quebrar por causa de um backup que falhou — mas o erro vai pro log,
    em vez de passar despercebido como antes).
    """
    BACKUPS_DIR.mkdir(exist_ok=True)
    destino = BACKUPS_DIR / f"investimentos_{dt.date.today().isoformat()}.db"
    fonte = "Turso (remoto)" if _e_turso() else "arquivo local"

    try:
        total = dump_para_arquivo(destino)
        log.info("Backup gerado a partir do %s: %s (%s linhas)", fonte, destino.name, total)
    except Exception as exc:  # noqa: BLE001 - backup nunca deve derrubar o app
        log.warning("Falha ao gerar backup a partir do %s: %s", fonte, exc)
        # Ultimo recurso: se existir arquivo local, pelo menos copia ele.
        if not _e_turso() and DB_PATH.exists():
            try:
                shutil.copy2(DB_PATH, destino)
                log.info("Backup gerado por copia simples do arquivo local: %s", destino.name)
            except OSError as exc_copia:
                log.warning("Falha tambem na copia simples: %s", exc_copia)
                return None
        else:
            return None

    _rotacionar()
    return destino


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    caminho = fazer_backup_banco()
    if caminho is None:
        raise SystemExit("Backup NAO foi gerado — veja o aviso acima.")
    print(f"OK: {caminho} ({caminho.stat().st_size:,} bytes)")
