"""Script headless (sem interface) para rodar via Tarefa Agendada do Windows,
apos o fechamento da B3, atualizando cotacoes, historico e proventos.

- Se APP_URL estiver configurado em config.env, loga no servidor hospedado
  (Render) com APP_USERNAME/APP_SENHA e dispara a atualizacao remota — e' o
  que mantem os dados atualizados quando o app esta na nuvem, sincronizado
  com o celular.
- Caso contrario, atualiza direto o banco local, como sempre funcionou.
"""
import os
import sys

import carregar_config

carregar_config.carregar()

APP_URL = os.environ.get("APP_URL", "").strip()


def _atualizar_remoto() -> None:
    import requests

    usuario = os.environ.get("APP_USERNAME", "")
    senha = os.environ.get("APP_SENHA", "")
    if not usuario or not senha:
        print("APP_URL configurado, mas APP_USERNAME/APP_SENHA faltando em config.env — abortando.")
        sys.exit(1)

    sessao = requests.Session()
    resp_login = sessao.post(f"{APP_URL}/api/auth/login", json={"username": usuario, "senha": senha}, timeout=30)
    if not resp_login.ok:
        print(f"Falha no login em {APP_URL}: {resp_login.status_code} {resp_login.text}")
        sys.exit(1)

    resp = sessao.post(f"{APP_URL}/api/atualizar", timeout=300)
    resp.raise_for_status()
    resultado = resp.json()
    print(f"[remoto] Atualizados: {resultado['atualizados']}")
    if resultado["com_erro"]:
        print(f"[remoto] Com erro: {resultado['com_erro']}")


def _atualizar_local() -> None:
    from app.updater import atualizar_tudo

    resultado = atualizar_tudo()
    print(f"[local] Atualizados: {resultado['atualizados']}")
    if resultado["com_erro"]:
        print(f"[local] Com erro: {resultado['com_erro']}")


if __name__ == "__main__":
    if APP_URL:
        _atualizar_remoto()
    else:
        _atualizar_local()
