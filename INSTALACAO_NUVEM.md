# Colocando o app na nuvem (desktop + celular sincronizados)

Siga na ordem. As contas são gratuitas e não pedem cartão de crédito. Sempre
que aparecer "só você pode fazer isso", é porque envolve criar uma conta —
eu não posso fazer isso por você.

## 1. Turso (banco de dados)

1. Acesse **https://turso.tech** e crie uma conta gratuita (só você pode
   fazer isso).
2. Depois de logado, crie um banco de dados novo (qualquer nome, ex:
   `meus-investimentos`).
3. Pegue duas informações que o painel do Turso mostra:
   - a **URL do banco** (algo como `libsql://meus-investimentos-SEUUSER.turso.io`)
   - um **auth token** (token de autenticação — geralmente tem um botão
     "Create Token" ou "Generate Token")
4. Guarde essas duas informações — vamos usá-las nos passos 3 e 4.

## 2. GitHub (guardar o código)

1. Acesse **https://github.com** e crie uma conta gratuita, se ainda não
   tiver (só você pode fazer isso).
2. Crie um repositório novo, público, com o nome que quiser (ex:
   `meus-investimentos`). Não marque nenhuma opção de "adicionar README" —
   o projeto já tem os arquivos.
3. Me avise quando tiver criado — eu conecto o projeto local a esse
   repositório e envio o código (nenhum dado pessoal seu vai junto: o
   `.gitignore` já impede isso).

## 3. Render (hospedar o backend)

1. Acesse **https://render.com** e crie uma conta gratuita, entrando com o
   GitHub do passo 2 (mais simples — já autoriza o acesso ao repositório).
2. No painel, clique em **New +** → **Web Service**.
3. Selecione o repositório `meus-investimentos` que você criou.
4. Preencha:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
5. Em **Environment Variables**, adicione três:
   - `TURSO_DATABASE_URL` → a URL do banco (passo 1)
   - `TURSO_AUTH_TOKEN` → o auth token (passo 1)
   - `SESSION_SECRET_KEY` → uma chave aleatória. Gere uma rodando isto no
     seu PC:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
6. Clique em **Create Web Service** e aguarde o deploy terminar (alguns
   minutos). Render vai te dar uma URL pública, tipo
   `https://meus-investimentos.onrender.com`.

**Nota sobre o plano gratuito do Render**: o servidor "dorme" depois de
15 minutos sem uso e demora ~30-50 segundos pra acordar na próxima vez que
alguém acessa. Normal e sem custo — só significa que o primeiro acesso do
dia pode demorar um pouco mais.

## 4. Configurar o app pra usar o servidor hospedado

1. Na pasta do projeto, copie `config.env.example` para `config.env`.
2. Preencha `APP_URL` com a URL que o Render te deu (passo 3.6).
3. Abra o app (`Abrir Meus Investimentos.bat`) — agora ele abre a URL
   hospedada em vez do servidor local. Crie seu usuário/senha na tela
   inicial (primeira vez que alguém usa esse servidor).
4. Volte no `config.env` e preencha `APP_USERNAME`/`APP_SENHA` com o mesmo
   usuário/senha que você acabou de criar — isso é o que permite a tarefa
   agendada diária atualizar os dados sozinha no servidor.

## 5. Instalar no celular

1. No navegador do celular (Chrome/Safari), acesse a mesma URL do Render.
2. Faça login com o usuário/senha do passo 4.3.
3. No menu do navegador, toque em **"Adicionar à tela inicial"** (Android)
   ou **"Adicionar à Tela de Início"** (iPhone, no botão de compartilhar).
4. Pronto — ícone próprio na tela inicial, abre em tela cheia como um app.

## Pronto — o que fica sincronizado

Depois desses 5 passos, tanto a janela desktop quanto o celular mostram os
mesmos dados em tempo real, porque os dois conversam com o mesmo servidor
(Render) e o mesmo banco (Turso). Qualquer atualização que eu fizer no
código e enviar pro GitHub, o Render aplica automaticamente no próximo
deploy — sem você precisar reinstalar nada em nenhum dos dois aparelhos.
