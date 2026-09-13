"""Script headless (sem interface) para rodar via Tarefa Agendada do Windows,
apos o fechamento da B3, atualizando cotacoes, historico e proventos.

- Se APP_URL estiver configurado em config.env, loga no servidor hospedado
  (Render) com APP_USERNAME/APP_SENHA e dispara a atualizacao remota — e' o
  que mantem os dados atualizados quando o app esta na nuvem, sincronizado
  com o celular.
- Caso contrario, atualiza direto o banco local, como sempre funcionou.

Em qualquer um dos dois casos o backup do banco e' gerado AQUI, nesta maquina.
Isso importa: com o app hospedado, quem rodava o backup era o servidor remoto,
gravando num disco efemero que se perde a cada deploy — ou seja, na pratica nao
havia backup nenhum. Agora o arquivo .db do dia cai na pasta backups/ local.
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


def _fazer_backup_local() -> None:
    """Gera o backup do dia na pasta backups/ desta maquina, lendo o banco que
    o app realmente usa (Turso, quando configurado)."""
    from app.backup import fazer_backup_banco

    caminho = fazer_backup_banco()
    if caminho is None:
        print("[backup] NAO foi possivel gerar o backup — veja atualizacao.log.")
    else:
        print(f"[backup] {caminho.name} ({caminho.stat().st_size:,} bytes)")


def _atualizar_local() -> None:
    from app.updater import atualizar_tudo

    resultado = atualizar_tudo()
    print(f"[local] Atualizados: {resultado['atualizados']}")
    if resultado["com_erro"]:
        print(f"[local] Com erro: {resultado['com_erro']}")


if __name__ == "__main__":
    if APP_URL:
        _atualizar_remoto()
        # No caminho local o backup ja acontece dentro de atualizar_tudo();
        # aqui, como a atualizacao roda no servidor, ele precisa ser feito
        # explicitamente desta maquina.
        _fazer_backup_local()
    else:
        _atualizar_local()
