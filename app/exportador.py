"""Exporta a carteira (posicoes, compras e proventos) para um arquivo Excel,
util para declaracao de imposto de renda ou planilhas proprias.

Gera o arquivo inteiramente em memoria (sem salvar em disco no servidor) e
devolve os bytes prontos para download — funciona igual rodando local ou
hospedado (no servidor hospedado o disco e' temporario, entao nunca faria
sentido depender de um arquivo salvo la)."""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Font

from .database import get_conn
from . import posicao as posicao_mod


def _cabecalho(ws, colunas: list[str]) -> None:
    ws.append(colunas)
    for cel in ws[1]:
        cel.font = Font(bold=True)


def exportar_carteira(usuario_id: int) -> bytes:
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT * FROM investimentos WHERE usuario_id = ? ORDER BY ticker, data_compra",
            (usuario_id,),
        ).fetchall()
        tickers_usuario = {l["ticker"] for l in lotes}
        cotacoes = {
            r["ticker"]: r for r in conn.execute("SELECT * FROM cotacoes_atuais").fetchall()
        }
        proventos = [
            dict(p) for p in conn.execute(
                "SELECT * FROM proventos_recebidos ORDER BY ticker, data_ex"
            ).fetchall()
            if p["ticker"] in tickers_usuario
        ]
        vendas = conn.execute(
            "SELECT * FROM vendas WHERE usuario_id = ? ORDER BY ticker, data_venda",
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()

    por_ticker: dict[str, list] = {}
    for lote in lotes:
        por_ticker.setdefault(lote["ticker"], []).append(lote)
    vendas_por_ticker: dict[str, list] = {}
    for venda in vendas:
        vendas_por_ticker.setdefault(venda["ticker"], []).append(venda)

    wb = Workbook()

    ws_posicoes = wb.active
    ws_posicoes.title = "Posições"
    _cabecalho(ws_posicoes, [
        "Ticker", "Tipo", "Quantidade", "Preço médio", "Valor investido",
        "Preço atual", "Valorização", "Proventos recebidos", "Ganho/perda em vendas", "Saldo total",
    ])
    for ticker, lotes_ticker in sorted(por_ticker.items()):
        tipo = lotes_ticker[0]["tipo"]
        cot = cotacoes.get(ticker)
        preco_atual = cot["preco_atual"] if cot else None
        prov_ticker = [p for p in proventos if p["ticker"] == ticker]

        pos = posicao_mod.calcular_posicao(lotes_ticker, vendas_por_ticker.get(ticker, []), prov_ticker, preco_atual)

        ws_posicoes.append([
            ticker, tipo, pos["quantidade_atual"], round(pos["preco_medio"], 4), round(pos["custo_remanescente"], 2),
            preco_atual, pos["valorizacao"], round(pos["proventos_recebidos_total"], 2),
            round(pos["ganho_realizado_vendas"], 2), pos["saldo_total"],
        ])

    ws_compras = wb.create_sheet("Compras")
    _cabecalho(ws_compras, ["Ticker", "Tipo", "Data da compra", "Quantidade", "Preço pago", "Valor total"])
    for lote in lotes:
        ws_compras.append([
            lote["ticker"], lote["tipo"], lote["data_compra"], lote["quantidade"],
            lote["preco_medio_compra"], round(lote["quantidade"] * lote["preco_medio_compra"], 2),
        ])

    ws_vendas = wb.create_sheet("Vendas")
    _cabecalho(ws_vendas, ["Ticker", "Data da venda", "Quantidade", "Preço unitário", "Valor total"])
    for v in vendas:
        ws_vendas.append([
            v["ticker"], v["data_venda"], v["quantidade"], v["preco_unitario"],
            round(v["quantidade"] * v["preco_unitario"], 2),
        ])

    ws_proventos = wb.create_sheet("Proventos recebidos")
    _cabecalho(ws_proventos, ["Ticker", "Data (ex)", "Valor por cota"])
    for p in proventos:
        ws_proventos.append([p["ticker"], p["data_ex"], p["valor_por_cota"]])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
