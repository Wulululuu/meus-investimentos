"""Ponto de entrada do app desktop: abre uma janela nativa apontando pro
backend certo.

- Se APP_URL estiver configurado em config.env, abre direto essa URL
  hospedada (Render) — desktop e celular passam a compartilhar os mesmos
  dados (Turso).
- Caso contrário, sobe um servidor local (como sempre funcionou) e abre a
  janela nele. Se o app já estiver aberto (porta ocupada por uma instância
  anterior), essa nova janela reaproveita o servidor existente em vez de
  tentar subir outro — antes, quando isso acontecia, a thread do servidor
  morria em silêncio e a janela abria com a interface toda vazia (sem
  gráficos, sem dados), sem nenhum aviso do motivo.
"""
import os

import carregar_config

carregar_config.carregar()  # precisa rodar ANTES de importar app.main (database.py lê os.environ no import)

import logging
import socket
import threading
import time

import webview

HOST = "127.0.0.1"
PORT = 8756

APP_URL = os.environ.get("APP_URL", "").strip()

log = logging.getLogger("run_app")


def _servidor_respondendo() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, PORT)) == 0


def iniciar_servidor_local():
    import uvicorn
    from app.main import app

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    except Exception:
        log.exception("Falha ao iniciar o servidor local")


if __name__ == "__main__":
    if APP_URL:
        url_janela = APP_URL
    else:
        from app.main import app  # também configura o logging (grava em atualizacao.log)

        if _servidor_respondendo():
            log.info("Porta %s já em uso — reaproveitando servidor de uma instância existente.", PORT)
        else:
            thread = threading.Thread(target=iniciar_servidor_local, daemon=True)
            thread.start()

            for _ in range(50):  # espera até 5s o servidor subir antes de abrir a janela
                if _servidor_respondendo():
                    break
                time.sleep(0.1)
            else:
                log.error("Servidor não respondeu a tempo na porta %s", PORT)

        url_janela = f"http://{HOST}:{PORT}"

    webview.create_window("Meus Investimentos", url_janela, width=1200, height=800)
    webview.start()
