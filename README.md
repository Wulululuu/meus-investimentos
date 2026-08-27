# Meus Investimentos

App desktop local para acompanhar ações, FIIs, ETFs e BDRs da B3: você cadastra
o ticker, a quantidade e o preço pago, e o app busca sozinho na internet o
preço atual, o histórico de preços, os proventos já recebidos e os próximos
proventos anunciados.

## Como usar

- Duplo clique em **"Abrir Meus Investimentos.bat"** para abrir o app.
- Clique em **"Registrar entrada"** (canto superior direito) e informe ticker,
  tipo, quantidade, preço médio de compra e data da compra.
- Clique em **"Registrar saída"** para anotar uma venda (veja a seção abaixo).
- Clique em uma linha da tabela para ver o gráfico de preço do ativo.
- Clique em **"Atualizar agora"** para forçar uma atualização manual.

## Atualização automática

Uma Tarefa Agendada do Windows chamada **"MeusInvestimentos-AtualizacaoDiaria"**
já foi criada, rodando todo dia às 19:00 (após o fechamento da B3) para
atualizar cotações e proventos sozinha, mesmo com o app fechado.

- Para ver/editar/remover: abra o **Agendador de Tarefas** do Windows e
  procure por esse nome.
- Log da última atualização automática: arquivo `atualizacao.log` nesta pasta.

## Compras em datas diferentes do mesmo ativo

Se você comprar o mesmo ticker mais de uma vez (em datas diferentes), o app
soma tudo automaticamente em um único item na tabela — quantidade total,
preço médio ponderado e valor total investido. Cada compra ("lote") continua
guardada individualmente por baixo dos panos, então os proventos recebidos são
calculados lote a lote (respeitando a data de cada compra) e depois somados, e
o mesmo vale para a valorização.

## Histórico de movimentação e registro de vendas

Clique na linha de um ativo para abrir o gráfico — logo abaixo aparece o
**histórico de movimentação**, com todas as compras e vendas daquele ativo
(data, quantidade, preço e valor total), mais recente primeiro. Cada linha
pode ser editada (ícone de lápis) ou removida. Se a lista for longa, a janela
rola verticalmente — ela nunca fica mais larga que a tela.

No canto superior direito, **"Registrar entrada"** adiciona uma compra e
**"Registrar saída"** registra uma venda (ambos pedem o ticker). Importante:
**vendas são só registro** — ao contrário das compras, elas **não alteram**
a quantidade possuída, a valorização, os proventos nem o saldo total
mostrados em nenhum outro lugar do app. Servem para você manter um diário de
negociações (útil, por exemplo, pra apuração de imposto de renda mais pra
frente), sem que o app tente recalcular sua posição sozinho.

## Aba "Patrimônio"

- **Evolução do patrimônio**: reconstrói, a partir do histórico de preços e das
  datas de cada compra, como seu patrimônio (valorização + proventos) e o
  valor investido evoluíram ao longo do tempo — mesmo para o período antes de
  você ter cadastrado o ativo no app.
- **Alocação por tipo**: gráfico de pizza mostrando quanto da carteira está em
  Ações, FIIs, ETFs e BDRs, pelo valor de mercado atual.
- **Meta de renda passiva**: defina um valor mensal de proventos como meta e
  acompanhe o progresso (barra de %), calculado pela média de proventos
  recebidos nos últimos 12 meses.

A aba "Minha Carteira" continua mostrando só os cards de resumo e a tabela
item a item, sem os gráficos.

## Editar uma compra

Dentro do gráfico de um ativo (clique na linha da tabela), cada compra listada
tem um ícone de lápis para editar quantidade, preço pago ou data — sem
precisar excluir e recadastrar.

## Exportar para Excel

O botão **"Exportar para Excel"** no topo gera um arquivo `.xlsx` (pasta
`exports/`) com quatro abas: posições consolidadas, todas as compras
individuais, todas as vendas registradas e todo o histórico de proventos
recebidos — útil para levar pra declaração de imposto de renda ou pra uma
planilha própria.

## Backup automático do banco

Toda vez que os dados são atualizados (manual ou pela tarefa diária), o app
salva uma cópia de `investimentos.db` na pasta `backups/`, com a data no
nome do arquivo. Mantém sempre os 14 backups mais recentes e apaga os mais
antigos automaticamente. Se algo corromper o banco principal, é só copiar o
backup mais recente de volta como `investimentos.db`.

## Fontes de dados (importante)

- **Preço atual, histórico de preços e proventos já pagos**: Yahoo Finance
  (gratuito, sem necessidade de cadastro ou token).
- **Próximos proventos (a receber + data prevista)**: StatusInvest, via um
  endpoint público não-oficial. Isso é "melhor esforço": funciona bem na
  prática, mas por não ser uma API documentada, pode eventualmente parar de
  funcionar se o site mudar. Se isso acontecer, o app simplesmente mostra
  "R$ 0,00 / —" nessa coluna em vez de quebrar — me avise que eu ajusto.
- Empresas costumam anunciar proventos poucas semanas antes do pagamento, então
  é normal a coluna "a receber (mês)" ficar zerada até o anúncio sair.

## Estrutura do projeto

- `app/main.py` — backend (FastAPI) com as rotas da API.
- `app/data_fetcher.py` — busca de dados no Yahoo Finance e StatusInvest.
- `app/updater.py` — grava os dados buscados no banco SQLite local.
- `app/patrimonio.py` — evolução do patrimônio e alocação por tipo.
- `app/exportador.py` — exportação da carteira para Excel.
- `app/database.py` — schema do banco (`investimentos.db`).
- `exports/` — arquivos `.xlsx` gerados pelo botão "Exportar para Excel".
- `backups/` — cópias diárias automáticas de `investimentos.db`.
- `app/static/` — interface (HTML/CSS/JS + gráfico via Chart.js).
- `run_app.py` — abre a janela desktop do app.
- `update_daily.py` — script sem interface usado pela tarefa agendada.
- `setup_task_scheduler.ps1` — (re)cria a tarefa agendada, se precisar.

## Reinstalar dependências

```bash
pip install -r requirements.txt
```
