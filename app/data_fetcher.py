"""
Busca dados de mercado (preco atual, historico, proventos) para ativos da B3.

Fontes:
- Yahoo Finance (query1.finance.yahoo.com): preco atual, historico de precos e
  proventos JA PAGOS (dividendos/JCP/rendimentos historicos). Nao exige token.
- StatusInvest (nao-oficial): proventos ANUNCIADOS/futuros com data de pagamento
  prevista. E' um endpoint publico nao documentado; se mudar ou falhar, o app
  degrada mostrando "nao disponivel" em vez de quebrar.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InvestimentosApp/1.0"}
_TIMEOUT = 15

_TIPO_PARA_PATH = {
    "Ação": "acao",
    "FII": "fii",
    "ETF": "etf",
    "BDR": "bdr",
}


@dataclass
class DadosAtivo:
    ticker: str
    nome: str | None = None
    preco_atual: float | None = None
    historico: list[tuple[str, float]] = field(default_factory=list)  # (YYYY-MM-DD, fechamento)
    proventos_pagos: list[tuple[str, float]] = field(default_factory=list)  # (YYYY-MM-DD, valor/cota)
    proventos_futuros: list[tuple[str, str, float]] = field(default_factory=list)  # (data_com, data_pgto, valor)
    erro: str | None = None


def buscar_preco_historico_e_proventos_pagos(ticker: str) -> DadosAtivo:
    dados = DadosAtivo(ticker=ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.SA"
    params = {"range": "2y", "interval": "1d", "events": "div,splits"}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        result = payload["chart"]["result"][0]
    except Exception as exc:  # rede, ticker inexistente, JSON inesperado, etc.
        dados.erro = f"Falha ao buscar cotacao/historico: {exc}"
        return dados

    meta = result.get("meta", {})
    dados.nome = meta.get("shortName") or meta.get("longName") or ticker
    dados.preco_atual = meta.get("regularMarketPrice")

    timestamps = result.get("timestamp") or []
    closes = (
        result.get("indicators", {})
        .get("quote", [{}])[0]
        .get("close", [])
    )
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        data_str = dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        dados.historico.append((data_str, round(float(close), 4)))

    eventos = result.get("events", {}) or {}
    for evento in (eventos.get("dividends") or {}).values():
        data_str = dt.datetime.utcfromtimestamp(evento["date"]).strftime("%Y-%m-%d")
        dados.proventos_pagos.append((data_str, float(evento["amount"])))
    dados.proventos_pagos.sort()

    return dados


def buscar_proventos_futuros(ticker: str, tipo: str) -> list[tuple[str, str, float]]:
    """Retorna proventos ANUNCIADOS com pagamento ainda nao realizado.

    Cada item: (data_com 'YYYY-MM-DD', data_pagamento 'YYYY-MM-DD' ou '', valor_por_cota).
    Lista vazia se a fonte falhar ou o tipo de ativo nao for suportado pela StatusInvest.
    """
    path = _TIPO_PARA_PATH.get(tipo)
    if not path:
        return []

    url = f"https://statusinvest.com.br/{path}/companytickerprovents"
    params = {"ticker": ticker, "chartProventsType": 2 if path in ("acao", "etf", "bdr") else 1}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        if not payload:
            return []
        modelos = payload.get("assetEarningsModels") or []
    except Exception:
        return []

    hoje = dt.date.today()
    futuros = []
    for item in modelos:
        try:
            data_com = _parse_data_br(item.get("ed"))
            data_pgto_raw = item.get("pd")
            data_pgto = _parse_data_br(data_pgto_raw) if data_pgto_raw else None
            valor = float(item.get("v") or 0)
        except (TypeError, ValueError):
            continue
        eh_futuro = (data_pgto and data_pgto >= hoje) or (data_pgto is None and data_com and data_com >= hoje)
        if eh_futuro and valor > 0:
            futuros.append((
                data_com.isoformat() if data_com else "",
                data_pgto.isoformat() if data_pgto else "",
                valor,
            ))
    futuros.sort(key=lambda x: x[1] or x[0])
    return futuros


def _parse_data_br(valor: str | None) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.datetime.strptime(valor, "%d/%m/%Y").date()
    except ValueError:
        return None
