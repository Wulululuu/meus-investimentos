"""Visoes agregadas da carteira ao longo do tempo: evolucao do patrimonio
(reconstruida a partir do historico de precos + compras/vendas) e alocacao
atual por tipo de ativo."""
from __future__ import annotations

from .database import get_conn
from . import posicao as posicao_mod


def historico_patrimonio(usuario_id: int) -> list[dict]:
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT ticker, quantidade, preco_medio_compra, data_compra FROM investimentos WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchall()
        if not lotes:
            return []
        vendas = conn.execute(
            "SELECT ticker, quantidade, preco_unitario, data_venda FROM vendas WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchall()

        tickers = sorted({l["ticker"] for l in lotes})
        lotes_por_ticker: dict[str, list] = {t: [] for t in tickers}
        for lote in lotes:
            lotes_por_ticker[lote["ticker"]].append(lote)
        vendas_por_ticker: dict[str, list] = {t: [] for t in tickers}
        for venda in vendas:
            vendas_por_ticker.setdefault(venda["ticker"], []).append(venda)

        precos_por_ticker: dict[str, dict[str, float]] = {}
        proventos_por_ticker: dict[str, list[tuple[str, float]]] = {}
        todas_datas: set[str] = set()

        for ticker in tickers:
            rows = conn.execute(
                "SELECT data, fechamento FROM historico_precos WHERE ticker = ? ORDER BY data",
                (ticker,),
            ).fetchall()
            precos_por_ticker[ticker] = {r["data"]: r["fechamento"] for r in rows}
            todas_datas.update(precos_por_ticker[ticker].keys())

            rows_prov = conn.execute(
                "SELECT data_ex, valor_por_cota FROM proventos_recebidos WHERE ticker = ? ORDER BY data_ex",
                (ticker,),
            ).fetchall()
            proventos_por_ticker[ticker] = [(r["data_ex"], r["valor_por_cota"]) for r in rows_prov]

        todas_datas.update(l["data_compra"] for l in lotes)
        todas_datas.update(v["data_venda"] for v in vendas)
        datas_ordenadas = sorted(todas_datas)
    finally:
        conn.close()

    # linha do tempo de quantidade (compras/vendas) e preco medio de cada ticker
    eventos_por_ticker: dict[str, list[tuple[str, float]]] = {}
    preco_medio_por_ticker: dict[str, float] = {}
    for ticker in tickers:
        eventos_por_ticker[ticker] = posicao_mod.linha_do_tempo(lotes_por_ticker[ticker], vendas_por_ticker[ticker])
        _, _, preco_medio_por_ticker[ticker] = posicao_mod.quantidade_bruta_e_preco_medio(lotes_por_ticker[ticker])

    # caixa recebido por ticker: proventos (ja' pesados pela quantidade em posse na
    # propria data-ex) + o valor de cada venda no dia dela. Somado cumulativamente
    # conforme a linha do tempo avanca — sem isso, o "patrimonio total" pareceria
    # cair quando na verdade a acao virou dinheiro (nao sumiu).
    eventos_caixa_por_ticker: dict[str, list[tuple[str, float]]] = {}
    for ticker in tickers:
        eventos = eventos_por_ticker[ticker]
        eventos_caixa = [
            (data_ex, valor_cota * posicao_mod.quantidade_em(eventos, data_ex))
            for data_ex, valor_cota in proventos_por_ticker[ticker]
        ]
        eventos_caixa += [
            (v["data_venda"], v["quantidade"] * v["preco_unitario"]) for v in vendas_por_ticker[ticker]
        ]
        eventos_caixa_por_ticker[ticker] = sorted(eventos_caixa, key=lambda e: e[0])
    indices_proventos = {t: 0 for t in tickers}
    proventos_acumulado_ticker = {t: 0.0 for t in tickers}

    ultimo_preco: dict[str, float | None] = {t: None for t in tickers}
    resultado = []

    for data in datas_ordenadas:
        for t in tickers:
            preco_do_dia = precos_por_ticker[t].get(data)
            if preco_do_dia is not None:
                ultimo_preco[t] = preco_do_dia

        valor_atual = 0.0
        valor_investido = 0.0
        caixa_total = 0.0

        for ticker in tickers:
            qtd = posicao_mod.quantidade_em(eventos_por_ticker[ticker], data)
            valor_investido += qtd * preco_medio_por_ticker[ticker]
            preco = ultimo_preco.get(ticker)
            if preco is not None:
                valor_atual += qtd * preco

            eventos_caixa = eventos_caixa_por_ticker[ticker]
            while indices_proventos[ticker] < len(eventos_caixa) and eventos_caixa[indices_proventos[ticker]][0] <= data:
                proventos_acumulado_ticker[ticker] += eventos_caixa[indices_proventos[ticker]][1]
                indices_proventos[ticker] += 1
            caixa_total += proventos_acumulado_ticker[ticker]

        resultado.append({
            "data": data,
            "valor_investido": round(valor_investido, 2),
            "valor_atual": round(valor_atual, 2),
            "caixa_recebido": round(caixa_total, 2),
            "patrimonio_total": round(valor_atual + caixa_total, 2),
        })

    return resultado


def alocacao_por_tipo(usuario_id: int) -> list[dict]:
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT ticker, tipo, quantidade, preco_medio_compra FROM investimentos "
            "WHERE usuario_id = ? ORDER BY ticker, data_compra",
            (usuario_id,),
        ).fetchall()
        vendas = conn.execute(
            "SELECT ticker, quantidade FROM vendas WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
        cotacoes = {
            r["ticker"]: r["preco_atual"]
            for r in conn.execute("SELECT ticker, preco_atual FROM cotacoes_atuais").fetchall()
        }
    finally:
        conn.close()

    # o tipo "oficial" de cada ticker e' o do primeiro lote cadastrado, igual ao
    # criterio usado na listagem principal (evita contar o mesmo ticker em dois
    # tipos caso o usuario tenha selecionado o tipo errado em uma compra extra)
    tipo_por_ticker: dict[str, str] = {}
    lotes_por_ticker: dict[str, list] = {}
    for lote in lotes:
        tipo_por_ticker.setdefault(lote["ticker"], lote["tipo"])
        lotes_por_ticker.setdefault(lote["ticker"], []).append(lote)
    vendido_por_ticker: dict[str, float] = {}
    for venda in vendas:
        vendido_por_ticker[venda["ticker"]] = vendido_por_ticker.get(venda["ticker"], 0.0) + venda["quantidade"]

    valor_por_tipo: dict[str, float] = {}
    for ticker, lotes_ticker in lotes_por_ticker.items():
        quantidade_bruta, _, preco_medio = posicao_mod.quantidade_bruta_e_preco_medio(lotes_ticker)
        quantidade_atual = quantidade_bruta - vendido_por_ticker.get(ticker, 0.0)
        if quantidade_atual <= 0:
            continue
        preco = cotacoes.get(ticker) or preco_medio
        tipo = tipo_por_ticker[ticker]
        valor_por_tipo[tipo] = valor_por_tipo.get(tipo, 0.0) + quantidade_atual * preco

    total = sum(valor_por_tipo.values())
    return [
        {"tipo": tipo, "valor": round(valor, 2), "pct": round(valor / total * 100, 2) if total else 0}
        for tipo, valor in sorted(valor_por_tipo.items(), key=lambda kv: -kv[1])
    ]
