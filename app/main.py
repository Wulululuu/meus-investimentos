from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .database import get_conn, init_db
from .updater import atualizar_tudo, atualizar_ticker
from . import patrimonio as patrimonio_mod
from . import exportador
from . import auth

app = FastAPI(title="Meus Investimentos")

STATIC_DIR = Path(__file__).resolve().parent / "static"

init_db()

ROTAS_PUBLICAS = {"/api/auth/status", "/api/auth/login", "/api/auth/registrar"}


class ExigirLoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/") and request.url.path not in ROTAS_PUBLICAS:
            if not request.session.get("usuario"):
                return JSONResponse({"detail": "Não autenticado"}, status_code=401)
        return await call_next(request)


app.add_middleware(ExigirLoginMiddleware)
# SessionMiddleware precisa ser o último adicionado para rodar ANTES do
# ExigirLoginMiddleware (no Starlette, o último middleware adicionado é o
# mais externo, ou seja, o primeiro a processar a requisição).
SESSION_SECRET = os.environ.get("SESSION_SECRET_KEY") or secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 30)


class NovoInvestimento(BaseModel):
    ticker: str
    tipo: str
    quantidade: float
    preco_medio_compra: float
    data_compra: str


@app.get("/")
def raiz():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Credenciais(BaseModel):
    username: str
    senha: str


@app.get("/api/auth/status")
def status_auth(request: Request):
    return {
        "precisa_configurar": not auth.existe_usuario(),
        "autenticado": bool(request.session.get("usuario")),
        "usuario": request.session.get("usuario"),
    }


@app.post("/api/auth/registrar")
def registrar(credenciais: Credenciais, request: Request):
    if auth.existe_usuario():
        raise HTTPException(403, "Já existe uma conta configurada neste app.")
    username = credenciais.username.strip()
    if not username or len(credenciais.senha) < 4:
        raise HTTPException(400, "Informe um usuário e uma senha com pelo menos 4 caracteres.")
    auth.criar_usuario(username, credenciais.senha)
    request.session["usuario"] = username
    return {"ok": True}


@app.post("/api/auth/login")
def login(credenciais: Credenciais, request: Request):
    if not auth.verificar_login(credenciais.username.strip(), credenciais.senha):
        raise HTTPException(401, "Usuário ou senha incorretos.")
    request.session["usuario"] = credenciais.username.strip()
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/investimentos")
def listar_investimentos():
    """Retorna uma posição consolidada por ticker, somando todos os lotes de
    compra (mesmo ativo comprado em datas diferentes vira um único item).
    Proventos recebidos são calculados lote a lote, respeitando a data de
    compra de cada lote, e depois somados."""
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT * FROM investimentos ORDER BY ticker, data_compra"
        ).fetchall()
        hoje = dt.date.today()
        inicio_mes = hoje.replace(day=1)
        if hoje.month == 12:
            fim_mes = hoje.replace(day=31)
        else:
            fim_mes = (hoje.replace(month=hoje.month + 1, day=1) - dt.timedelta(days=1))

        por_ticker: dict[str, list] = {}
        for lote in lotes:
            por_ticker.setdefault(lote["ticker"], []).append(lote)

        resultado = []
        for ticker, lotes_ticker in por_ticker.items():
            tipo = lotes_ticker[0]["tipo"]
            quantidade_total = sum(l["quantidade"] for l in lotes_ticker)
            custo_total = sum(l["quantidade"] * l["preco_medio_compra"] for l in lotes_ticker)
            preco_medio = custo_total / quantidade_total if quantidade_total else 0
            data_compra_mais_antiga = min(l["data_compra"] for l in lotes_ticker)

            cot = conn.execute(
                "SELECT * FROM cotacoes_atuais WHERE ticker = ?", (ticker,)
            ).fetchone()
            preco_atual = cot["preco_atual"] if cot else None
            nome = cot["nome_curto"] if cot else None
            atualizado_em = cot["atualizado_em"] if cot else None

            proventos_rows = conn.execute(
                "SELECT data_ex, valor_por_cota FROM proventos_recebidos "
                "WHERE ticker = ? ORDER BY data_ex",
                (ticker,),
            ).fetchall()
            proventos_recebidos_total = 0.0
            for lote in lotes_ticker:
                por_cota_desde_compra = sum(
                    r["valor_por_cota"] for r in proventos_rows if r["data_ex"] >= lote["data_compra"]
                )
                proventos_recebidos_total += por_cota_desde_compra * lote["quantidade"]

            futuros_rows = conn.execute(
                "SELECT data_com, data_pagamento, valor_por_cota FROM proventos_futuros "
                "WHERE ticker = ? ORDER BY data_pagamento",
                (ticker,),
            ).fetchall()
            proventos_mes_atual = [
                dict(r) for r in futuros_rows
                if r["data_pagamento"] and inicio_mes.isoformat() <= r["data_pagamento"] <= fim_mes.isoformat()
            ]
            valor_a_receber_mes = sum(
                r["valor_por_cota"] * quantidade_total for r in proventos_mes_atual
            )

            valorizacao = None
            valorizacao_pct = None
            saldo_total = None
            saldo_total_pct = None
            if preco_atual is not None:
                valorizacao = preco_atual * quantidade_total - custo_total
                valorizacao_pct = (preco_atual / preco_medio - 1) * 100 if preco_medio else None
                saldo_total = valorizacao + proventos_recebidos_total
                saldo_total_pct = (saldo_total / custo_total * 100) if custo_total else None

            resultado.append({
                "ticker": ticker,
                "tipo": tipo,
                "nome": nome,
                "quantidade": quantidade_total,
                "preco_medio_compra": preco_medio,
                "valor_investido": custo_total,
                "data_compra": data_compra_mais_antiga,
                "num_compras": len(lotes_ticker),
                "preco_atual": preco_atual,
                "atualizado_em": atualizado_em,
                "valorizacao": valorizacao,
                "valorizacao_pct": valorizacao_pct,
                "proventos_recebidos_total": proventos_recebidos_total,
                "proventos_a_receber_mes": valor_a_receber_mes,
                "proventos_a_receber_detalhe": proventos_mes_atual,
                "saldo_total": saldo_total,
                "saldo_total_pct": saldo_total_pct,
            })
        resultado.sort(key=lambda r: r["ticker"])
        return resultado
    finally:
        conn.close()


@app.get("/api/investimentos/{ticker}/movimentacoes")
def listar_movimentacoes(ticker: str):
    """Histórico de compras e vendas de um ticker, mais recente primeiro.
    Vendas são só registro histórico — não afetam quantidade nem saldo em
    nenhum outro lugar do app."""
    ticker = ticker.upper()
    conn = get_conn()
    try:
        compras = conn.execute(
            "SELECT id, quantidade, preco_medio_compra, data_compra FROM investimentos "
            "WHERE ticker = ? ORDER BY data_compra",
            (ticker,),
        ).fetchall()
        vendas = conn.execute(
            "SELECT id, quantidade, preco_unitario, data_venda FROM vendas "
            "WHERE ticker = ? ORDER BY data_venda",
            (ticker,),
        ).fetchall()
    finally:
        conn.close()

    movimentacoes = [
        {
            "id": c["id"],
            "tipo": "Compra",
            "data": c["data_compra"],
            "quantidade": c["quantidade"],
            "preco_unitario": c["preco_medio_compra"],
            "valor_total": round(c["quantidade"] * c["preco_medio_compra"], 2),
        }
        for c in compras
    ] + [
        {
            "id": v["id"],
            "tipo": "Venda",
            "data": v["data_venda"],
            "quantidade": v["quantidade"],
            "preco_unitario": v["preco_unitario"],
            "valor_total": round(v["quantidade"] * v["preco_unitario"], 2),
        }
        for v in vendas
    ]
    movimentacoes.sort(key=lambda m: m["data"], reverse=True)
    return movimentacoes


class NovaVenda(BaseModel):
    quantidade: float
    preco_unitario: float
    data_venda: str


@app.post("/api/investimentos/{ticker}/vendas")
def registrar_venda(ticker: str, venda: NovaVenda):
    if venda.quantidade <= 0 or venda.preco_unitario <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO vendas (ticker, quantidade, preco_unitario, data_venda) VALUES (?, ?, ?, ?)",
            (ticker.upper(), venda.quantidade, venda.preco_unitario, venda.data_venda),
        )
        conn.commit()
        novo_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": novo_id}


@app.put("/api/vendas/{venda_id}")
def editar_venda(venda_id: int, venda: NovaVenda):
    if venda.quantidade <= 0 or venda.preco_unitario <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE vendas SET quantidade = ?, preco_unitario = ?, data_venda = ? WHERE id = ?",
            (venda.quantidade, venda.preco_unitario, venda.data_venda, venda_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Venda não encontrada")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.delete("/api/vendas/{venda_id}")
def remover_venda(venda_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM vendas WHERE id = ?", (venda_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


class EdicaoInvestimento(BaseModel):
    quantidade: float
    preco_medio_compra: float
    data_compra: str


@app.put("/api/investimentos/{investimento_id}")
def editar_investimento(investimento_id: int, dados: EdicaoInvestimento):
    if dados.quantidade <= 0 or dados.preco_medio_compra <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")

    conn = get_conn()
    try:
        cur = conn.execute(
            """UPDATE investimentos SET quantidade = ?, preco_medio_compra = ?, data_compra = ?
               WHERE id = ?""",
            (dados.quantidade, dados.preco_medio_compra, dados.data_compra, investimento_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Compra não encontrada")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/investimentos")
def criar_investimento(inv: NovoInvestimento):
    ticker = inv.ticker.strip().upper()
    if not ticker:
        raise HTTPException(400, "Ticker obrigatório")
    if inv.tipo not in ("Ação", "FII", "ETF", "BDR"):
        raise HTTPException(400, "Tipo inválido")
    if inv.quantidade <= 0 or inv.preco_medio_compra <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")

    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO investimentos (ticker, tipo, quantidade, preco_medio_compra, data_compra)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, inv.tipo, inv.quantidade, inv.preco_medio_compra, inv.data_compra),
        )
        conn.commit()
        novo_id = cur.lastrowid
    finally:
        conn.close()

    erro = atualizar_ticker(ticker, inv.tipo)
    return {"id": novo_id, "aviso": erro}


@app.delete("/api/investimentos/{investimento_id}")
def remover_investimento(investimento_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM investimentos WHERE id = ?", (investimento_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/historico/{ticker}")
def historico_ticker(ticker: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT data, fechamento FROM historico_precos WHERE ticker = ? ORDER BY data",
            (ticker.upper(),),
        ).fetchall()
        return [{"data": r["data"], "fechamento": r["fechamento"]} for r in rows]
    finally:
        conn.close()


@app.post("/api/atualizar")
def atualizar_agora():
    return atualizar_tudo()


@app.get("/api/patrimonio/historico")
def patrimonio_historico():
    return patrimonio_mod.historico_patrimonio()


@app.get("/api/alocacao")
def alocacao():
    return patrimonio_mod.alocacao_por_tipo()


class MetaRenda(BaseModel):
    valor: float


@app.get("/api/meta-renda")
def obter_meta_renda():
    conn = get_conn()
    try:
        row = conn.execute("SELECT valor FROM meta WHERE chave = 'meta_renda_mensal'").fetchone()
        meta_mensal = float(row["valor"]) if row else None

        lotes = conn.execute(
            "SELECT ticker, quantidade, data_compra FROM investimentos"
        ).fetchall()
        um_ano_atras = (dt.date.today() - dt.timedelta(days=365)).isoformat()
        renda_12m = 0.0
        for lote in lotes:
            desde = max(um_ano_atras, lote["data_compra"])
            rows = conn.execute(
                "SELECT valor_por_cota FROM proventos_recebidos WHERE ticker = ? AND data_ex >= ?",
                (lote["ticker"], desde),
            ).fetchall()
            renda_12m += sum(r["valor_por_cota"] for r in rows) * lote["quantidade"]
    finally:
        conn.close()

    renda_media_mensal = renda_12m / 12
    progresso_pct = (renda_media_mensal / meta_mensal * 100) if meta_mensal else None
    return {
        "meta_mensal": meta_mensal,
        "renda_media_mensal": round(renda_media_mensal, 2),
        "progresso_pct": round(progresso_pct, 1) if progresso_pct is not None else None,
    }


@app.post("/api/meta-renda")
def definir_meta_renda(meta: MetaRenda):
    if meta.valor <= 0:
        raise HTTPException(400, "Informe um valor maior que zero")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO meta (chave, valor) VALUES ('meta_renda_mensal', ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (str(meta.valor),),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/exportar")
def exportar_carteira():
    caminho = exportador.exportar_carteira()
    return {"arquivo": str(caminho)}


@app.post("/api/exportar/abrir-pasta")
def abrir_pasta_exportacao():
    exportador.EXPORTS_DIR.mkdir(exist_ok=True)
    os.startfile(exportador.EXPORTS_DIR)  # noqa: S606 - app desktop local, pasta do próprio usuário
    return {"ok": True}


@app.get("/api/status")
def status():
    conn = get_conn()
    try:
        row = conn.execute("SELECT valor FROM meta WHERE chave = 'ultima_atualizacao'").fetchone()
        return {"ultima_atualizacao": row["valor"] if row else None}
    finally:
        conn.close()
