"""Atualiza cotacoes, historico e proventos no banco local para todos os
tickers cadastrados. Usado tanto pelo botao 'Atualizar agora' quanto pela
tarefa agendada diaria."""
from __future__ import annotations

import datetime as dt
import logging
import shutil

from pathlib import Path

from . import data_fetcher
from .database import DB_PATH, get_conn

LOG_PATH = Path(__file__).resolve().parent.parent / "atualizacao.log"
BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUPS_PARA_MANTER = 14

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("updater")


def fazer_backup_banco() -> None:
    """Copia o banco de dados para backups/, mantendo apenas os N mais recentes."""
    if not DB_PATH.exists():
        return
    BACKUPS_DIR.mkdir(exist_ok=True)
    destino = BACKUPS_DIR / f"investimentos_{dt.date.today().isoformat()}.db"
    try:
        shutil.copy2(DB_PATH, destino)
    except OSError as exc:
        log.warning("Falha ao criar backup do banco: %s", exc)
        return

    backups = sorted(BACKUPS_DIR.glob("investimentos_*.db"))
    for antigo in backups[:-BACKUPS_PARA_MANTER]:
        antigo.unlink(missing_ok=True)


def tickers_cadastrados() -> list[tuple[str, str]]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT DISTINCT ticker, tipo FROM investimentos").fetchall()
        return [(r["ticker"], r["tipo"]) for r in rows]
    finally:
        conn.close()


def atualizar_ticker(ticker: str, tipo: str) -> str | None:
    """Busca e persiste os dados de um ticker. Retorna mensagem de erro (ou None)."""
    dados = data_fetcher.buscar_preco_historico_e_proventos_pagos(ticker)
    conn = get_conn()
    try:
        if dados.erro:
            log.warning("Erro ao atualizar %s: %s", ticker, dados.erro)
            return dados.erro

        agora = dt.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """INSERT INTO cotacoes_atuais (ticker, nome_curto, preco_atual, atualizado_em)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                 nome_curto=excluded.nome_curto,
                 preco_atual=excluded.preco_atual,
                 atualizado_em=excluded.atualizado_em""",
            (ticker, dados.nome, dados.preco_atual, agora),
        )

        conn.executemany(
            """INSERT INTO historico_precos (ticker, data, fechamento) VALUES (?, ?, ?)
               ON CONFLICT(ticker, data) DO UPDATE SET fechamento=excluded.fechamento""",
            [(ticker, data, fechamento) for data, fechamento in dados.historico],
        )

        conn.executemany(
            """INSERT INTO proventos_recebidos (ticker, data_ex, valor_por_cota) VALUES (?, ?, ?)
               ON CONFLICT(ticker, data_ex) DO UPDATE SET valor_por_cota=excluded.valor_por_cota""",
            [(ticker, data, valor) for data, valor in dados.proventos_pagos],
        )

        futuros = data_fetcher.buscar_proventos_futuros(ticker, tipo)
        conn.execute("DELETE FROM proventos_futuros WHERE ticker = ?", (ticker,))
        conn.executemany(
            """INSERT INTO proventos_futuros (ticker, data_com, data_pagamento, valor_por_cota, atualizado_em)
               VALUES (?, ?, ?, ?, ?)""",
            [(ticker, com, pgto, valor, agora) for com, pgto, valor in futuros],
        )

        conn.commit()
        log.info("Atualizado %s: preco=%s, %d pontos historico, %d proventos futuros",
                  ticker, dados.preco_atual, len(dados.historico), len(futuros))
        return None
    finally:
        conn.close()


def atualizar_tudo() -> dict:
    """Atualiza todos os tickers cadastrados. Retorna resumo do resultado."""
    resultado = {"atualizados": [], "com_erro": {}}
    for ticker, tipo in tickers_cadastrados():
        erro = atualizar_ticker(ticker, tipo)
        if erro:
            resultado["com_erro"][ticker] = erro
        else:
            resultado["atualizados"].append(ticker)

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO meta (chave, valor) VALUES ('ultima_atualizacao', ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (dt.datetime.now().isoformat(timespec="seconds"),),
        )
        conn.commit()
    finally:
        conn.close()

    fazer_backup_banco()

    return resultado
