"""Visoes agregadas da carteira ao longo do tempo: evolucao do patrimonio
(reconstruida a partir do historico de precos + datas de compra) e alocacao
atual por tipo de ativo."""
from __future__ import annotations

import bisect

from .database import get_conn


def historico_patrimonio(usuario_id: int) -> list[dict]:
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT ticker, quantidade, preco_medio_compra, data_compra FROM investimentos WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchall()
        if not lotes:
            return []

        tickers = sorted({l["ticker"] for l in lotes})
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
        datas_ordenadas = sorted(todas_datas)
    finally:
        conn.close()

    # ponteiro (indice) de proventos por lote, comecando na primeira data_ex >= data_compra do lote
    indices_proventos = []
    for lote in lotes:
        datas_prov = [d for d, _ in proventos_por_ticker[lote["ticker"]]]
        indices_proventos.append(bisect.bisect_left(datas_prov, lote["data_compra"]))
    proventos_acumulado_lote = [0.0] * len(lotes)

    ultimo_preco: dict[str, float | None] = {t: None for t in tickers}
    resultado = []

    for data in datas_ordenadas:
        for t in tickers:
            preco_do_dia = precos_por_ticker[t].get(data)
            if preco_do_dia is not None:
                ultimo_preco[t] = preco_do_dia

        valor_atual = 0.0
        valor_investido = 0.0
        proventos_total = 0.0

        for i, lote in enumerate(lotes):
            if lote["data_compra"] > data:
                continue
            valor_investido += lote["quantidade"] * lote["preco_medio_compra"]
            preco = ultimo_preco.get(lote["ticker"])
            if preco is not None:
                valor_atual += lote["quantidade"] * preco

            lista_prov = proventos_por_ticker[lote["ticker"]]
            while indices_proventos[i] < len(lista_prov) and lista_prov[indices_proventos[i]][0] <= data:
                proventos_acumulado_lote[i] += lista_prov[indices_proventos[i]][1] * lote["quantidade"]
                indices_proventos[i] += 1
            proventos_total += proventos_acumulado_lote[i]

        resultado.append({
            "data": data,
            "valor_investido": round(valor_investido, 2),
            "valor_atual": round(valor_atual, 2),
            "proventos_acumulados": round(proventos_total, 2),
            "patrimonio_total": round(valor_atual + proventos_total, 2),
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
    for lote in lotes:
        tipo_por_ticker.setdefault(lote["ticker"], lote["tipo"])

    valor_por_tipo: dict[str, float] = {}
    for lote in lotes:
        preco = cotacoes.get(lote["ticker"]) or lote["preco_medio_compra"]
        tipo = tipo_por_ticker[lote["ticker"]]
        valor_por_tipo[tipo] = valor_por_tipo.get(tipo, 0.0) + lote["quantidade"] * preco

    total = sum(valor_por_tipo.values())
    return [
        {"tipo": tipo, "valor": round(valor, 2), "pct": round(valor / total * 100, 2) if total else 0}
        for tipo, valor in sorted(valor_por_tipo.items(), key=lambda kv: -kv[1])
    ]
