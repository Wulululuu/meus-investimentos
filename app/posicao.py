"""Calculo da posicao de um ticker (quantidade, preco medio, proventos e
ganhos), levando em conta compras E vendas.

Convencao (a mesma do metodo de "preco medio" usado no Brasil para IR sobre
renda variavel): o custo de referencia e' a media ponderada de TODAS as
compras, e essa media nao muda quando voce vende parte da posicao — tanto o
ganho realizado de uma venda quanto o valor investido remanescente usam essa
mesma media.

Uma venda passa a reduzir a quantidade em posse (e o valor investido junto),
mas os proventos recebidos e o ganho da propria venda continuam contando
para o saldo total — nada do que ja aconteceu "desaparece" so' porque o
ativo foi vendido depois.
"""
from __future__ import annotations


def quantidade_bruta_e_preco_medio(lotes) -> tuple[float, float, float]:
    """(quantidade comprada, custo total bruto, preco medio) a partir dos
    lotes de compra de UM ticker."""
    quantidade = sum(l["quantidade"] for l in lotes)
    custo_total = sum(l["quantidade"] * l["preco_medio_compra"] for l in lotes)
    preco_medio = custo_total / quantidade if quantidade else 0.0
    return quantidade, custo_total, preco_medio


def linha_do_tempo(lotes, vendas) -> list[tuple[str, float]]:
    """Lista ordenada de (data, variacao_de_quantidade) de UM ticker —
    compras somam, vendas subtraem."""
    eventos = [(l["data_compra"], l["quantidade"]) for l in lotes]
    eventos += [(v["data_venda"], -v["quantidade"]) for v in vendas]
    eventos.sort(key=lambda e: e[0])
    return eventos


def quantidade_em(eventos: list[tuple[str, float]], data: str) -> float:
    """Quantidade em posse ate (e incluindo) `data`, segundo a linha do
    tempo de compras/vendas."""
    return sum(delta for d, delta in eventos if d <= data)


def calcular_posicao(lotes, vendas, proventos_rows, preco_atual: float | None) -> dict:
    """Calcula a posicao consolidada de UM ticker.

    lotes: rows de `investimentos` (quantidade, preco_medio_compra,
    data_compra, ...) desse ticker.
    vendas: rows de `vendas` (quantidade, preco_unitario, data_venda) desse
    mesmo ticker.
    proventos_rows: rows de `proventos_recebidos` (data_ex, valor_por_cota)
    desse mesmo ticker.
    preco_atual: cotacao atual, ou None se ainda nao disponivel.
    """
    quantidade_bruta, custo_total_bruto, preco_medio = quantidade_bruta_e_preco_medio(lotes)
    quantidade_vendida = sum(v["quantidade"] for v in vendas)
    quantidade_atual = quantidade_bruta - quantidade_vendida
    custo_remanescente = preco_medio * quantidade_atual

    ganho_realizado_vendas = sum(
        (v["preco_unitario"] - preco_medio) * v["quantidade"] for v in vendas
    )

    eventos = linha_do_tempo(lotes, vendas)
    proventos_recebidos_total = sum(
        r["valor_por_cota"] * quantidade_em(eventos, r["data_ex"]) for r in proventos_rows
    )

    valorizacao = None
    saldo_total = None
    if preco_atual is not None:
        valorizacao = preco_atual * quantidade_atual - custo_remanescente
        saldo_total = valorizacao + proventos_recebidos_total + ganho_realizado_vendas

    return {
        "quantidade_atual": quantidade_atual,
        "preco_medio": preco_medio,
        "custo_total_bruto": custo_total_bruto,
        "custo_remanescente": custo_remanescente,
        "ganho_realizado_vendas": ganho_realizado_vendas,
        "proventos_recebidos_total": proventos_recebidos_total,
        "valorizacao": valorizacao,
        "saldo_total": saldo_total,
    }
