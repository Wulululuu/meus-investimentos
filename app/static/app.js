const fmtMoeda = (v) =>
  v === null || v === undefined
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtPct = (v) =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

const fmtData = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

const classeSinal = (v) => (v === null || v === undefined ? "" : v >= 0 ? "positivo" : "negativo");

let graficoAtual = null;
let graficoPatrimonio = null;
let graficoAlocacao = null;

async function carregarInvestimentos() {
  const resp = await fetch("/api/investimentos");
  const investimentos = await resp.json();
  renderizarResumo(investimentos);
  renderizarTabela(investimentos);
}

function carregarAbaPatrimonio() {
  carregarPatrimonioHistorico();
  carregarAlocacao();
  carregarMetaRenda();
}

function renderizarResumo(investimentos) {
  const custoTotal = investimentos.reduce((s, i) => s + (i.valor_investido ?? 0), 0);
  const saldoTotal = investimentos.reduce((s, i) => s + (i.saldo_total ?? 0), 0);
  const proventosTotal = investimentos.reduce((s, i) => s + (i.proventos_recebidos_total ?? 0), 0);
  const aReceberMes = investimentos.reduce((s, i) => s + (i.proventos_a_receber_mes ?? 0), 0);
  const saldoPct = custoTotal ? (saldoTotal / custoTotal) * 100 : null;

  const cards = [
    { rotulo: "Investido (preço de compra)", valor: fmtMoeda(custoTotal) },
    { rotulo: "Proventos recebidos", valor: fmtMoeda(proventosTotal) },
    { rotulo: "A receber este mês", valor: fmtMoeda(aReceberMes) },
    {
      rotulo: "Saldo total (valorização + proventos)",
      valor: `${fmtMoeda(saldoTotal)} (${fmtPct(saldoPct)})`,
      classe: classeSinal(saldoTotal),
    },
  ];

  document.getElementById("resumo-geral").innerHTML = cards
    .map(
      (c) => `<div class="card">
        <div class="rotulo">${c.rotulo}</div>
        <div class="valor ${c.classe ?? ""}">${c.valor}</div>
      </div>`
    )
    .join("");
}

function renderizarTabela(investimentos) {
  const corpo = document.getElementById("tabela-corpo");
  if (investimentos.length === 0) {
    corpo.innerHTML = `<tr><td colspan="9" class="muted" style="text-align:center;padding:32px">
      Nenhum investimento cadastrado ainda. Clique em "+ Novo investimento".</td></tr>`;
    return;
  }

  corpo.innerHTML = investimentos
    .map((inv) => {
      const proxima = inv.proventos_a_receber_detalhe?.[0];
      const dataPrevista = proxima ? fmtData(proxima.data_pagamento) : null;
      return `<tr data-ticker="${inv.ticker}">
        <td>
          <div class="ticker-nome">${inv.ticker} <span class="ticker-sub">${inv.tipo}</span></div>
          <div class="ticker-sub">${inv.nome ?? ""}</div>
        </td>
        <td>${inv.quantidade}</td>
        <td>${fmtMoeda(inv.preco_medio_compra)}</td>
        <td>${fmtMoeda(inv.preco_atual)}</td>
        <td>${fmtMoeda(inv.valor_investido)}</td>
        <td class="${classeSinal(inv.valorizacao)}">
          ${fmtMoeda(inv.valorizacao)}<br><span class="ticker-sub">${fmtPct(inv.valorizacao_pct)}</span>
        </td>
        <td>${fmtMoeda(inv.proventos_recebidos_total)}</td>
        <td>${fmtMoeda(inv.proventos_a_receber_mes)}${dataPrevista ? `<br><span class="ticker-sub">em ${dataPrevista}</span>` : ""}</td>
        <td class="${classeSinal(inv.saldo_total)}">
          ${fmtMoeda(inv.saldo_total)}<br><span class="ticker-sub">${fmtPct(inv.saldo_total_pct)}</span>
        </td>
      </tr>`;
    })
    .join("");

  corpo.querySelectorAll("tr[data-ticker]").forEach((tr) => {
    tr.addEventListener("click", () => abrirGrafico(tr.dataset.ticker));
  });
}

async function renderizarMovimentacoes(ticker) {
  const resp = await fetch(`/api/investimentos/${ticker}/movimentacoes`);
  const movimentacoes = await resp.json();
  const corpo = document.getElementById("compras-corpo");

  if (movimentacoes.length === 0) {
    corpo.innerHTML = `<tr><td colspan="7" class="muted" style="text-align:center;padding:16px">Nenhuma movimentação registrada.</td></tr>`;
    return;
  }

  corpo.innerHTML = movimentacoes
    .map((m) => {
      const badge = m.tipo === "Compra" ? "badge-compra" : "badge-venda";
      const endpoint = m.tipo === "Compra" ? "investimentos" : "vendas";
      return `<tr data-mov-id="${m.id}" data-mov-tipo="${m.tipo}" data-mov-endpoint="${endpoint}">
        <td><span class="badge-tipo ${badge}">${m.tipo}</span></td>
        <td>${fmtData(m.data)}</td>
        <td>${m.quantidade}</td>
        <td>${fmtMoeda(m.preco_unitario)}</td>
        <td>${fmtMoeda(m.valor_total)}</td>
        <td><button class="btn-editar" data-editar-mov title="Editar">&#9998;</button></td>
        <td><button class="btn-remover" data-remover-mov title="Remover">&times;</button></td>
      </tr>`;
    })
    .join("");

  corpo.querySelectorAll("[data-remover-mov]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const tr = btn.closest("tr");
      const rotulo = tr.dataset.movTipo === "Compra" ? "esta compra" : "este registro de venda";
      if (!confirm(`Remover ${rotulo}?`)) return;
      await fetch(`/api/${tr.dataset.movEndpoint}/${tr.dataset.movId}`, { method: "DELETE" });
      await renderizarMovimentacoes(ticker);
      carregarInvestimentos();
    });
  });

  corpo.querySelectorAll("[data-editar-mov]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tr = btn.closest("tr");
      const mov = movimentacoes.find((m) => m.id === Number(tr.dataset.movId) && m.tipo === tr.dataset.movTipo);
      abrirEdicaoMovimentacao(mov, ticker);
    });
  });
}

function abrirEdicaoMovimentacao(mov, ticker) {
  const tr = document.querySelector(`#compras-corpo tr[data-mov-id="${mov.id}"][data-mov-tipo="${mov.tipo}"]`);
  const endpoint = mov.tipo === "Compra" ? "investimentos" : "vendas";
  tr.classList.add("lote-edicao");
  tr.innerHTML = `
    <td><span class="badge-tipo ${mov.tipo === "Compra" ? "badge-compra" : "badge-venda"}">${mov.tipo}</span></td>
    <td><input type="date" value="${mov.data}" data-campo="data" /></td>
    <td><input type="number" step="any" min="0.000001" value="${mov.quantidade}" data-campo="quantidade" /></td>
    <td><input type="number" step="any" min="0.01" value="${mov.preco_unitario}" data-campo="preco" /></td>
    <td colspan="3">
      <div class="acoes-edicao">
        <button class="btn-salvar-lote" data-salvar-mov>Salvar</button>
        <button type="button" class="btn-cancelar-lote" data-cancelar-mov>Cancelar</button>
      </div>
    </td>`;

  tr.querySelector("[data-cancelar-mov]").addEventListener("click", () => renderizarMovimentacoes(ticker));

  tr.querySelector("[data-salvar-mov]").addEventListener("click", async () => {
    const quantidade = parseFloat(tr.querySelector('[data-campo="quantidade"]').value);
    const preco = parseFloat(tr.querySelector('[data-campo="preco"]').value);
    const data = tr.querySelector('[data-campo="data"]').value;
    const dados = mov.tipo === "Compra"
      ? { quantidade, preco_medio_compra: preco, data_compra: data }
      : { quantidade, preco_unitario: preco, data_venda: data };

    const resp = await fetch(`/api/${endpoint}/${mov.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    if (!resp.ok) {
      alert("Erro ao salvar");
      return;
    }
    await renderizarMovimentacoes(ticker);
    await carregarInvestimentos();
  });
}

async function abrirGrafico(ticker) {
  const resp = await fetch(`/api/historico/${ticker}`);
  const historico = await resp.json();
  document.getElementById("grafico-titulo").textContent = ticker;
  document.getElementById("modal-grafico").classList.remove("oculto");
  renderizarMovimentacoes(ticker);

  const ctx = document.getElementById("grafico-canvas");
  if (graficoAtual) graficoAtual.destroy();
  graficoAtual = new Chart(ctx, {
    type: "line",
    data: {
      labels: historico.map((h) => fmtData(h.data)),
      datasets: [
        {
          label: `${ticker} — preço de fechamento`,
          data: historico.map((h) => h.fechamento),
          borderColor: "#4f7cff",
          backgroundColor: "rgba(79,124,255,0.15)",
          fill: true,
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#e8ecf4" } } },
      scales: {
        x: { ticks: { color: "#8b95ab", maxTicksLimit: 12 }, grid: { color: "#2a3348" } },
        y: { ticks: { color: "#8b95ab" }, grid: { color: "#2a3348" } },
      },
    },
  });
}

function mostrarErroCarregamento(idCanvas, mensagem) {
  const canvas = document.getElementById(idCanvas);
  const container = canvas.parentElement;
  canvas.classList.add("oculto");
  let aviso = container.querySelector(".aviso-carregamento");
  if (!aviso) {
    aviso = document.createElement("p");
    aviso.className = "muted aviso-carregamento";
    container.appendChild(aviso);
  }
  aviso.textContent = mensagem;
}

function limparErroCarregamento(idCanvas) {
  const canvas = document.getElementById(idCanvas);
  canvas.classList.remove("oculto");
  canvas.parentElement.querySelector(".aviso-carregamento")?.remove();
}

async function carregarPatrimonioHistorico() {
  let pontos;
  try {
    const resp = await fetch("/api/patrimonio/historico");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    pontos = await resp.json();
  } catch (err) {
    mostrarErroCarregamento("patrimonio-canvas", "Não foi possível carregar o gráfico. Verifique se o app está aberto corretamente e tente atualizar.");
    return;
  }

  const ctx = document.getElementById("patrimonio-canvas");
  if (graficoPatrimonio) graficoPatrimonio.destroy();

  if (pontos.length === 0) {
    mostrarErroCarregamento("patrimonio-canvas", "Nenhum dado de histórico ainda. Cadastre um investimento e atualize.");
    return;
  }
  limparErroCarregamento("patrimonio-canvas");

  graficoPatrimonio = new Chart(ctx, {
    type: "line",
    data: {
      labels: pontos.map((p) => fmtData(p.data)),
      datasets: [
        {
          label: "Valor investido",
          data: pontos.map((p) => p.valor_investido),
          borderColor: "#8b95ab",
          borderDash: [4, 4],
          pointRadius: 0,
          tension: 0,
        },
        {
          label: "Patrimônio (valorização + proventos)",
          data: pontos.map((p) => p.patrimonio_total),
          borderColor: "#2ecc71",
          backgroundColor: "rgba(46,204,113,0.12)",
          fill: true,
          pointRadius: 0,
          tension: 0.1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#e8ecf4", boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: "#8b95ab", maxTicksLimit: 8 }, grid: { color: "#2a3348" } },
        y: { ticks: { color: "#8b95ab" }, grid: { color: "#2a3348" } },
      },
    },
  });
}

const CORES_TIPO = { "Ação": "#4f7cff", "FII": "#2ecc71", "ETF": "#e8c874", "BDR": "#e74c3c" };

async function carregarAlocacao() {
  let dados;
  try {
    const resp = await fetch("/api/alocacao");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    dados = await resp.json();
  } catch (err) {
    mostrarErroCarregamento("alocacao-canvas", "Não foi possível carregar. Tente atualizar.");
    return;
  }

  const ctx = document.getElementById("alocacao-canvas");
  if (graficoAlocacao) graficoAlocacao.destroy();
  if (dados.length === 0) {
    mostrarErroCarregamento("alocacao-canvas", "Nenhum investimento cadastrado ainda.");
    return;
  }
  limparErroCarregamento("alocacao-canvas");

  graficoAlocacao = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: dados.map((d) => `${d.tipo} (${d.pct}%)`),
      datasets: [
        {
          data: dados.map((d) => d.valor),
          backgroundColor: dados.map((d) => CORES_TIPO[d.tipo] ?? "#8b95ab"),
          borderColor: "#171e2e",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { color: "#e8ecf4", boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

async function carregarMetaRenda() {
  const el = document.getElementById("meta-renda-conteudo");
  let dados;
  try {
    const resp = await fetch("/api/meta-renda");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    dados = await resp.json();
  } catch (err) {
    el.innerHTML = `<p class="muted">Não foi possível carregar. Tente atualizar.</p>`;
    return;
  }

  if (!dados.meta_mensal) {
    el.innerHTML = `<p class="muted">Renda média atual: <strong>${fmtMoeda(dados.renda_media_mensal)}</strong>/mês.
      Defina uma meta abaixo para ver o progresso.</p>`;
    return;
  }

  const pct = Math.min(dados.progresso_pct ?? 0, 100);
  el.innerHTML = `
    <div class="valor-atual">${fmtMoeda(dados.renda_media_mensal)} <span class="muted" style="font-size:13px">/ mês</span></div>
    <div class="meta-sub">${dados.progresso_pct}% da meta de ${fmtMoeda(dados.meta_mensal)}/mês (média dos últimos 12 meses)</div>
    <div class="barra-progresso">
      <div class="barra-progresso-preenchimento ${pct >= 100 ? "completa" : ""}" style="width:${pct}%"></div>
    </div>`;
}

document.getElementById("form-meta-renda").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const valor = parseFloat(new FormData(ev.target).get("valor"));
  if (!valor || valor <= 0) return;
  await fetch("/api/meta-renda", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valor }),
  });
  ev.target.reset();
  await carregarMetaRenda();
});

document.getElementById("btn-exportar").addEventListener("click", () => {
  // Navegar pra essa URL não sai da página — o cabeçalho Content-Disposition
  // do backend faz o navegador só baixar o arquivo (funciona local ou hospedado).
  window.location.href = "/api/exportar";
});

async function carregarStatus() {
  const resp = await fetch("/api/status");
  const status = await resp.json();
  const el = document.getElementById("ultima-atualizacao");
  el.textContent = status.ultima_atualizacao
    ? `Última atualização: ${new Date(status.ultima_atualizacao).toLocaleString("pt-BR")}`
    : "Ainda não atualizado";
}

document.getElementById("btn-atualizar").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  ev.target.textContent = "Atualizando...";
  try {
    await fetch("/api/atualizar", { method: "POST" });
    await carregarInvestimentos();
    await carregarStatus();
  } finally {
    ev.target.disabled = false;
    ev.target.textContent = "Atualizar agora";
  }
});

document.getElementById("btn-registrar-entrada").addEventListener("click", () => {
  document.getElementById("modal-novo").classList.remove("oculto");
});

document.getElementById("btn-registrar-saida").addEventListener("click", () => {
  document.getElementById("modal-saida").classList.remove("oculto");
});

document.querySelectorAll("[data-fechar]").forEach((btn) => {
  btn.addEventListener("click", () => {
    btn.closest(".modal").classList.add("oculto");
  });
});

document.getElementById("form-novo").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const form = ev.target;
  const dados = Object.fromEntries(new FormData(form).entries());
  dados.quantidade = parseFloat(dados.quantidade);
  dados.preco_medio_compra = parseFloat(dados.preco_medio_compra);
  dados.ticker = dados.ticker.toUpperCase();

  const erroEl = document.getElementById("form-erro");
  erroEl.classList.add("oculto");

  const resp = await fetch("/api/investimentos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });

  if (!resp.ok) {
    const err = await resp.json();
    erroEl.textContent = err.detail || "Erro ao salvar";
    erroEl.classList.remove("oculto");
    return;
  }

  form.reset();
  document.getElementById("modal-novo").classList.add("oculto");
  await carregarInvestimentos();
  await carregarStatus();
});

document.getElementById("form-saida").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const form = ev.target;
  const dados = Object.fromEntries(new FormData(form).entries());
  const ticker = dados.ticker.toUpperCase();
  delete dados.ticker;
  dados.quantidade = parseFloat(dados.quantidade);
  dados.preco_unitario = parseFloat(dados.preco_unitario);

  const erroEl = document.getElementById("form-saida-erro");
  erroEl.classList.add("oculto");

  const resp = await fetch(`/api/investimentos/${ticker}/vendas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });

  if (!resp.ok) {
    const err = await resp.json();
    erroEl.textContent = err.detail || "Erro ao registrar saída";
    erroEl.classList.remove("oculto");
    return;
  }

  form.reset();
  document.getElementById("modal-saida").classList.add("oculto");
});

document.querySelectorAll(".aba-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".aba-btn").forEach((b) => b.classList.remove("ativa"));
    btn.classList.add("ativa");
    document.getElementById("aba-carteira").classList.toggle("oculto", btn.dataset.aba !== "carteira");
    document.getElementById("aba-patrimonio").classList.toggle("oculto", btn.dataset.aba !== "patrimonio");
    if (btn.dataset.aba === "patrimonio") {
      carregarAbaPatrimonio();
    }
  });
});

document.getElementById("btn-sair").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  location.reload();
});

async function enviarLogin(acao) {
  const form = document.getElementById("form-login");
  if (!form.reportValidity()) return;

  const dados = Object.fromEntries(new FormData(form).entries());
  const erroEl = document.getElementById("login-erro");
  erroEl.classList.add("oculto");

  const resp = await fetch(`/api/auth/${acao}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });

  if (!resp.ok) {
    const err = await resp.json();
    erroEl.textContent = err.detail || "Erro ao entrar";
    erroEl.classList.remove("oculto");
    return;
  }

  iniciarApp(dados.username);
}

document.getElementById("form-login").addEventListener("submit", (ev) => {
  ev.preventDefault();
  enviarLogin("login");
});

document.getElementById("btn-login-criar-conta").addEventListener("click", () => {
  enviarLogin("registrar");
});

function iniciarApp(nomeUsuario) {
  document.getElementById("tela-login").classList.add("oculto");
  document.getElementById("app-conteudo").classList.remove("oculto");
  if (nomeUsuario) document.getElementById("usuario-logado").textContent = nomeUsuario;
  carregarInvestimentos();
  carregarStatus();
}

async function bootstrap() {
  const resp = await fetch("/api/auth/status");
  const dados = await resp.json();

  if (dados.autenticado) {
    iniciarApp(dados.usuario);
    return;
  }

  document.getElementById("tela-login").classList.remove("oculto");
}

bootstrap();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  });
}
