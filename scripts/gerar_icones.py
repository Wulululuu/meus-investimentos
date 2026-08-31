"""Gera os icones do app (PWA + favicon + janela desktop) a partir da
imagem que o usuario escolheu (cifrao verde 3D + grafico em alta + moedas).

A imagem original vem com um fundo em xadrez cinza "gravado" nos pixels
(nao e' transparencia de verdade — o arquivo e' um .jpeg, que nem suporta
alpha). Esse script remove esse fundo (por cor + limpeza da franja de
ruido de compressao jpeg nas bordas das linhas finas), recorta um
quadrado centrado no cifrao e gera todos os tamanhos precisando de icone
no app.

Roda uma vez, manualmente, quando quiser trocar o visual do icone.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

RAIZ = Path(__file__).resolve().parent.parent
ICONES_DIR = RAIZ / "app" / "static" / "icons"
ICONES_DIR.mkdir(parents=True, exist_ok=True)

FONTE = Path(__file__).resolve().parent / "assets" / "logo_fonte.jpeg"
BG_TRANSPARENTE = (0, 0, 0, 0)
BG_SOLIDO = (15, 20, 32, 255)  # --bg do app — so' usado no icone maskable


def _remover_fundo_xadrez(im: Image.Image) -> Image.Image:
    arr = np.array(im.convert("RGB")).astype(float)
    maxc, minc = arr.max(axis=2), arr.min(axis=2)
    sat = maxc - minc

    cor_a, cor_b = np.array([193, 193, 193.0]), np.array([251, 251, 251.0])
    dist_a = np.linalg.norm(arr - cor_a, axis=2)
    dist_b = np.linalg.norm(arr - cor_b, axis=2)
    candidato = (dist_a < 22) | (dist_b < 12)

    rotulos, _ = ndimage.label(candidato, structure=np.ones((3, 3), dtype=int))
    tamanhos = np.bincount(rotulos.ravel())
    tamanhos[0] = 0
    mascara = np.isin(rotulos, np.where(tamanhos > 40)[0])

    # limpa a franja cinza de ringing do jpeg colada nas bordas das linhas
    # finas pretas, que sobra colada no fundo ja removido
    cinza_generico = (sat < 15) & (maxc > 50)
    for _ in range(4):
        dilatado = ndimage.binary_dilation(mascara, iterations=3)
        mascara = mascara | (dilatado & cinza_generico)

    alpha = ndimage.gaussian_filter(np.where(mascara, 0.0, 255.0), sigma=1.0)
    return Image.fromarray(np.dstack([arr, alpha]).astype(np.uint8), mode="RGBA")


def _sobre_fundo(recorte: Image.Image, tamanho: int, escala_conteudo: float, fundo=BG_TRANSPARENTE) -> Image.Image:
    canvas = Image.new("RGBA", (tamanho, tamanho), fundo)
    conteudo_tam = round(tamanho * escala_conteudo)
    conteudo = recorte.resize((conteudo_tam, conteudo_tam), Image.LANCZOS)
    offset = (tamanho - conteudo_tam) // 2
    canvas.paste(conteudo, (offset, offset), conteudo)
    return canvas


def gerar() -> None:
    bruto = Image.open(FONTE)
    sem_fundo = _remover_fundo_xadrez(bruto)

    # recorte quadrado centrado no cifrao (a imagem original e' 896x1200)
    recorte = sem_fundo.crop((0, 255, 896, 1151))

    icon_512 = _sobre_fundo(recorte, 512, 1.0)
    icon_512.save(ICONES_DIR / "icon-512.png")

    icon_192 = _sobre_fundo(recorte, 192, 1.0)
    icon_192.save(ICONES_DIR / "icon-192.png")

    # o icone "maskable" precisa de fundo solido — o Android recorta ele
    # num formato (circulo, squircle etc) e um fundo transparente deixa
    # buracos/artefatos nesse recorte
    icon_maskable = _sobre_fundo(recorte, 512, 0.65, fundo=BG_SOLIDO)
    icon_maskable.save(ICONES_DIR / "icon-maskable-512.png")

    # o icone da tela inicial do iOS tambem precisa de fundo solido — o
    # Safari nao preenche transparencia, ela vira preto no icone real
    apple_touch_icon = _sobre_fundo(recorte, 180, 1.0, fundo=BG_SOLIDO)
    apple_touch_icon.save(ICONES_DIR / "apple-touch-icon.png")

    tamanhos_ico = [(16, 16), (32, 32), (48, 48), (256, 256)]
    icon_512.save(RAIZ / "app" / "static" / "favicon.ico", format="ICO", sizes=tamanhos_ico)
    icon_512.save(RAIZ / "icone_app.ico", format="ICO", sizes=tamanhos_ico)

    print("Icones gerados em", ICONES_DIR)


if __name__ == "__main__":
    gerar()
