from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .database import get_conn, init_db
from .updater import atualizar_tudo, atualizar_ticker
from . import patrimonio as patrimonio_mod
from . import posicao as posicao_mod
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


def usuario_id_atual(request: Request) -> int:
    # Garantido presente pelo ExigirLoginMiddleware em toda rota protegida.
    return request.session["usuario_id"]


@app.get("/api/auth/status")
def status_auth(request: Request):
    return {
        "autenticado": bool(request.session.get("usuario")),
        "usuario": request.session.get("usuario"),
    }


@app.post("/api/auth/registrar")
def registrar(credenciais: Credenciais, request: Request):
    username = credenciais.username.strip()
    if not username or len(credenciais.senha) < 4:
        raise HTTPException(400, "Informe um usuário e uma senha com pelo menos 4 caracteres.")
    if not auth.username_disponivel(username):
        raise HTTPException(409, "Esse nome de usuário já está em uso — escolha outro.")
    novo_id = auth.criar_usuario(username, credenciais.senha)
    request.session["usuario"] = username
    request.session["usuario_id"] = novo_id
    return {"ok": True}


@app.post("/api/auth/login")
def login(credenciais: Credenciais, request: Request):
    usuario_id = auth.obter_usuario_id(credenciais.username.strip(), credenciais.senha)
    if usuario_id is None:
        raise HTTPException(401, "Usuário ou senha incorretos.")
    request.session["usuario"] = credenciais.username.strip()
    request.session["usuario_id"] = usuario_id
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/investimentos")
def listar_investimentos(usuario_id: int = Depends(usuario_id_atual)):
    """Retorna uma posição consolidada por ticker, somando todos os lotes de
    compra (mesmo ativo comprado em datas diferentes vira um único item).
    Vendas reduzem a quantidade em posse (e o valor investido junto), mas os
    proventos recebidos até a data de cada venda e o ganho realizado dela
    continuam contando para o saldo total — ver app/posicao.py."""
    conn = get_conn()
    try:
        lotes = conn.execute(
            "SELECT * FROM investimentos WHERE usuario_id = ? ORDER BY ticker, data_compra",
            (usuario_id,),
        ).fetchall()
        vendas = conn.execute(
            "SELECT * FROM vendas WHERE usuario_id = ? ORDER BY ticker, data_venda",
            (usuario_id,),
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
        vendas_por_ticker: dict[str, list] = {}
        for venda in vendas:
            vendas_por_ticker.setdefault(venda["ticker"], []).append(venda)

        resultado = []
        for ticker, lotes_ticker in por_ticker.items():
            tipo = lotes_ticker[0]["tipo"]
            vendas_ticker = vendas_por_ticker.get(ticker, [])
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
            posicao = posicao_mod.calcular_posicao(lotes_ticker, vendas_ticker, proventos_rows, preco_atual)

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
                r["valor_por_cota"] * posicao["quantidade_atual"] for r in proventos_mes_atual
            )

            valorizacao_pct = (
                (preco_atual / posicao["preco_medio"] - 1) * 100
                if preco_atual is not None and posicao["preco_medio"]
                else None
            )
            saldo_total_pct = (
                (posicao["saldo_total"] / posicao["custo_total_bruto"] * 100)
                if posicao["saldo_total"] is not None and posicao["custo_total_bruto"]
                else None
            )

            resultado.append({
                "ticker": ticker,
                "tipo": tipo,
                "nome": nome,
                "quantidade": posicao["quantidade_atual"],
                "preco_medio_compra": posicao["preco_medio"],
                "valor_investido": posicao["custo_remanescente"],
                "data_compra": data_compra_mais_antiga,
                "num_compras": len(lotes_ticker),
                "preco_atual": preco_atual,
                "atualizado_em": atualizado_em,
                "valorizacao": posicao["valorizacao"],
                "valorizacao_pct": valorizacao_pct,
                "proventos_recebidos_total": posicao["proventos_recebidos_total"],
                "ganho_realizado_vendas": posicao["ganho_realizado_vendas"],
                "proventos_a_receber_mes": valor_a_receber_mes,
                "proventos_a_receber_detalhe": proventos_mes_atual,
                "saldo_total": posicao["saldo_total"],
                "saldo_total_pct": saldo_total_pct,
            })
        resultado.sort(key=lambda r: r["ticker"])
        return resultado
    finally:
        conn.close()


@app.get("/api/investimentos/{ticker}/movimentacoes")
def listar_movimentacoes(ticker: str, usuario_id: int = Depends(usuario_id_atual)):
    """Histórico de compras e vendas de um ticker, mais recente primeiro.
    Vendas reduzem a quantidade em posse — ver posicao.calcular_posicao."""
    ticker = ticker.upper()
    conn = get_conn()
    try:
        compras = conn.execute(
            "SELECT id, quantidade, preco_medio_compra, data_compra FROM investimentos "
            "WHERE ticker = ? AND usuario_id = ? ORDER BY data_compra",
            (ticker, usuario_id),
        ).fetchall()
        vendas = conn.execute(
            "SELECT id, quantidade, preco_unitario, data_venda FROM vendas "
            "WHERE ticker = ? AND usuario_id = ? ORDER BY data_venda",
            (ticker, usuario_id),
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


def _quantidade_disponivel(conn, ticker: str, usuario_id: int, *, ignorar_venda_id: int | None = None) -> float:
    """Quantidade em posse do ticker (comprada - ja vendida), usada para
    impedir vender mais do que se tem. `ignorar_venda_id` exclui a propria
    venda sendo editada da conta do ja-vendido."""
    comprada = conn.execute(
        "SELECT COALESCE(SUM(quantidade), 0) AS q FROM investimentos WHERE ticker = ? AND usuario_id = ?",
        (ticker, usuario_id),
    ).fetchone()["q"]
    query_vendida = "SELECT COALESCE(SUM(quantidade), 0) AS q FROM vendas WHERE ticker = ? AND usuario_id = ?"
    params = [ticker, usuario_id]
    if ignorar_venda_id is not None:
        query_vendida += " AND id != ?"
        params.append(ignorar_venda_id)
    vendida = conn.execute(query_vendida, params).fetchone()["q"]
    return comprada - vendida


@app.post("/api/investimentos/{ticker}/vendas")
def registrar_venda(ticker: str, venda: NovaVenda, usuario_id: int = Depends(usuario_id_atual)):
    if venda.quantidade <= 0 or venda.preco_unitario <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")
    ticker = ticker.upper()
    conn = get_conn()
    try:
        disponivel = _quantidade_disponivel(conn, ticker, usuario_id)
        if venda.quantidade > disponivel:
            raise HTTPException(400, f"Você tem {disponivel:g} de {ticker} — não é possível vender {venda.quantidade:g}")
        cur = conn.execute(
            "INSERT INTO vendas (ticker, quantidade, preco_unitario, data_venda, usuario_id) VALUES (?, ?, ?, ?, ?)",
            (ticker, venda.quantidade, venda.preco_unitario, venda.data_venda, usuario_id),
        )
        conn.commit()
        novo_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": novo_id}


@app.put("/api/vendas/{venda_id}")
def editar_venda(venda_id: int, venda: NovaVenda, usuario_id: int = Depends(usuario_id_atual)):
    if venda.quantidade <= 0 or venda.preco_unitario <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")
    conn = get_conn()
    try:
        atual = conn.execute(
            "SELECT ticker FROM vendas WHERE id = ? AND usuario_id = ?", (venda_id, usuario_id)
        ).fetchone()
        if atual is None:
            raise HTTPException(404, "Venda não encontrada")
        disponivel = _quantidade_disponivel(conn, atual["ticker"], usuario_id, ignorar_venda_id=venda_id)
        if venda.quantidade > disponivel:
            raise HTTPException(
                400, f"Você tem {disponivel:g} de {atual['ticker']} — não é possível vender {venda.quantidade:g}"
            )
        conn.execute(
            "UPDATE vendas SET quantidade = ?, preco_unitario = ?, data_venda = ? WHERE id = ? AND usuario_id = ?",
            (venda.quantidade, venda.preco_unitario, venda.data_venda, venda_id, usuario_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.delete("/api/vendas/{venda_id}")
def remover_venda(venda_id: int, usuario_id: int = Depends(usuario_id_atual)):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM vendas WHERE id = ? AND usuario_id = ?", (venda_id, usuario_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


class EdicaoInvestimento(BaseModel):
    quantidade: float
    preco_medio_compra: float
    data_compra: str


def _checar_nao_deixa_vendas_orfas(conn, ticker: str, usuario_id: int, quantidade_bruta_apos: float) -> None:
    """Impede editar/remover uma compra de um jeito que deixaria a
    quantidade comprada menor que a ja vendida (venda "orfa", sem lastro)."""
    vendida = conn.execute(
        "SELECT COALESCE(SUM(quantidade), 0) AS q FROM vendas WHERE ticker = ? AND usuario_id = ?",
        (ticker, usuario_id),
    ).fetchone()["q"]
    if quantidade_bruta_apos < vendida:
        raise HTTPException(
            400,
            f"Isso deixaria {vendida:g} de {ticker} vendido sem ter sido comprado "
            f"(só sobrariam {quantidade_bruta_apos:g}) — ajuste ou remova alguma venda primeiro.",
        )


@app.put("/api/investimentos/{investimento_id}")
def editar_investimento(investimento_id: int, dados: EdicaoInvestimento, usuario_id: int = Depends(usuario_id_atual)):
    if dados.quantidade <= 0 or dados.preco_medio_compra <= 0:
        raise HTTPException(400, "Quantidade e preço devem ser maiores que zero")

    conn = get_conn()
    try:
        atual = conn.execute(
            "SELECT ticker, quantidade FROM investimentos WHERE id = ? AND usuario_id = ?",
            (investimento_id, usuario_id),
        ).fetchone()
        if atual is None:
            raise HTTPException(404, "Compra não encontrada")

        outras_compras = conn.execute(
            "SELECT COALESCE(SUM(quantidade), 0) AS q FROM investimentos "
            "WHERE ticker = ? AND usuario_id = ? AND id != ?",
            (atual["ticker"], usuario_id, investimento_id),
        ).fetchone()["q"]
        _checar_nao_deixa_vendas_orfas(conn, atual["ticker"], usuario_id, outras_compras + dados.quantidade)

        conn.execute(
            """UPDATE investimentos SET quantidade = ?, preco_medio_compra = ?, data_compra = ?
               WHERE id = ? AND usuario_id = ?""",
            (dados.quantidade, dados.preco_medio_compra, dados.data_compra, investimento_id, usuario_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/investimentos")
def criar_investimento(inv: NovoInvestimento, usuario_id: int = Depends(usuario_id_atual)):
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
            """INSERT INTO investimentos (ticker, tipo, quantidade, preco_medio_compra, data_compra, usuario_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, inv.tipo, inv.quantidade, inv.preco_medio_compra, inv.data_compra, usuario_id),
        )
        conn.commit()
        novo_id = cur.lastrowid
    finally:
        conn.close()

    erro = atualizar_ticker(ticker, inv.tipo)
    return {"id": novo_id, "aviso": erro}


@app.delete("/api/investimentos/{investimento_id}")
def remover_investimento(investimento_id: int, usuario_id: int = Depends(usuario_id_atual)):
    conn = get_conn()
    try:
        atual = conn.execute(
            "SELECT ticker, quantidade FROM investimentos WHERE id = ? AND usuario_id = ?",
            (investimento_id, usuario_id),
        ).fetchone()
        if atual is None:
            raise HTTPException(404, "Compra não encontrada")

        outras_compras = conn.execute(
            "SELECT COALESCE(SUM(quantidade), 0) AS q FROM investimentos "
            "WHERE ticker = ? AND usuario_id = ? AND id != ?",
            (atual["ticker"], usuario_id, investimento_id),
        ).fetchone()["q"]
        _checar_nao_deixa_vendas_orfas(conn, atual["ticker"], usuario_id, outras_compras)

        conn.execute("DELETE FROM investimentos WHERE id = ? AND usuario_id = ?", (investimento_id, usuario_id))
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
def patrimonio_historico(usuario_id: int = Depends(usuario_id_atual)):
    return patrimonio_mod.historico_patrimonio(usuario_id)


@app.get("/api/alocacao")
def alocacao(usuario_id: int = Depends(usuario_id_atual)):
    return patrimonio_mod.alocacao_por_tipo(usuario_id)


class MetaRenda(BaseModel):
    valor: float


def _chave_meta_renda(usuario_id: int) -> str:
    return f"meta_renda_mensal:{usuario_id}"


@app.get("/api/meta-renda")
def obter_meta_renda(usuario_id: int = Depends(usuario_id_atual)):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT valor FROM meta WHERE chave = ?", (_chave_meta_renda(usuario_id),)
        ).fetchone()
        meta_mensal = float(row["valor"]) if row else None

        lotes = conn.execute(
            "SELECT ticker, quantidade, data_compra FROM investimentos WHERE usuario_id = ?",
            (usuario_id,),
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
def definir_meta_renda(meta: MetaRenda, usuario_id: int = Depends(usuario_id_atual)):
    if meta.valor <= 0:
        raise HTTPException(400, "Informe um valor maior que zero")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO meta (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (_chave_meta_renda(usuario_id), str(meta.valor)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/exportar")
def exportar_carteira(usuario_id: int = Depends(usuario_id_atual)):
    conteudo = exportador.exportar_carteira(usuario_id)
    nome_arquivo = f"carteira_{dt.date.today().isoformat()}.xlsx"
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@app.get("/api/status")
def status():
    conn = get_conn()
    try:
        row = conn.execute("SELECT valor FROM meta WHERE chave = 'ultima_atualizacao'").fetchone()
        return {"ultima_atualizacao": row["valor"] if row else None}
    finally:
        conn.close()
