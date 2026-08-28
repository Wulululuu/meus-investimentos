"""Gera os icones do app (PWA + janela desktop) a partir de formas
desenhadas com Pillow: cifrao verde sobre um grafico de barras em alta,
com moedas douradas — no mesmo estilo/paleta do app (fundo #0f1420,
verde #2ecc71).

Roda uma vez, manualmente, quando quiser trocar o visual do icone.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
ICONES_DIR = RAIZ / "app" / "static" / "icons"
ICONES_DIR.mkdir(parents=True, exist_ok=True)

BG = (15, 20, 32, 255)        # --bg
VERDE = (46, 204, 113, 255)   # --verde
VERDE_ESCURO = (33, 150, 83, 255)
DOURADO = (240, 190, 90, 255)
DOURADO_ESCURO = (200, 150, 60, 255)
BRANCO = (232, 236, 244, 255)

FONTE_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def _desenhar_base(tamanho: int, *, com_fundo: bool, escala_conteudo: float) -> Image.Image:
    """Desenha o icone num canvas grande (para depois reduzir com anti-aliasing).

    escala_conteudo < 1 encolhe o desenho em direcao ao centro (usado no
    icone "maskable", que precisa de uma margem de seguranca porque o SO
    recorta o icone em formatos variados).
    """
    S = 2048  # desenha em alta resolucao e reduz no final
    img = Image.new("RGBA", (S, S), BG if com_fundo else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = S / 2, S / 2

    def esc(x: float, y: float) -> tuple[float, float]:
        return (cx + (x - cx) * escala_conteudo, cy + (y - cy) * escala_conteudo)

    # --- grafico de barras em alta (base do desenho) ---
    n_barras = 5
    largura_barra = S * 0.09
    espaco = S * 0.045
    base_y = S * 0.78
    alturas = [0.16, 0.26, 0.36, 0.48, 0.62]
    x0 = S * 0.10
    for i, h in enumerate(alturas):
        x = x0 + i * (largura_barra + espaco)
        topo = base_y - S * h
        p0 = esc(x, base_y)
        p1 = esc(x + largura_barra, topo)
        cor = VERDE if i % 2 == 0 else VERDE_ESCURO
        draw.rectangle([min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])], fill=cor)

    # --- seta ascendente por cima das barras ---
    seta_pts = [
        esc(S * 0.08, S * 0.62),
        esc(S * 0.34, S * 0.42),
        esc(S * 0.50, S * 0.52),
        esc(S * 0.80, S * 0.20),
    ]
    largura_linha = int(S * 0.028 * escala_conteudo)
    draw.line(seta_pts, fill=BRANCO, width=largura_linha, joint="curve")
    # ponta da seta
    ponta = esc(S * 0.80, S * 0.20)
    direcao = esc(S * 0.68, S * 0.30)
    ang = math.atan2(ponta[1] - direcao[1], ponta[0] - direcao[0])
    tam_ponta = S * 0.075 * escala_conteudo
    p_a = (ponta[0] - tam_ponta * math.cos(ang - math.radians(28)), ponta[1] - tam_ponta * math.sin(ang - math.radians(28)))
    p_b = (ponta[0] - tam_ponta * math.cos(ang + math.radians(28)), ponta[1] - tam_ponta * math.sin(ang + math.radians(28)))
    draw.polygon([ponta, p_a, p_b], fill=BRANCO)

    # --- moedas douradas caindo ---
    moedas = [(S * 0.72, S * 0.62, 0.11), (S * 0.85, S * 0.50, 0.085), (S * 0.62, S * 0.74, 0.07)]
    for mx, my, mr in moedas:
        raio = S * mr * escala_conteudo
        centro = esc(mx, my)
        draw.ellipse([centro[0] - raio, centro[1] - raio, centro[0] + raio, centro[1] + raio], fill=DOURADO, outline=DOURADO_ESCURO, width=max(2, int(raio * 0.12)))

    # --- cifrao verde, elemento principal, por cima de tudo ---
    fonte_tam = int(S * 0.62 * escala_conteudo)
    fonte = ImageFont.truetype(FONTE_BOLD, fonte_tam)
    texto = "$"
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1] - S * 0.02 * escala_conteudo
    contorno = max(2, int(S * 0.012 * escala_conteudo))
    draw.text((tx, ty), texto, font=fonte, fill=VERDE, stroke_width=contorno, stroke_fill=(10, 14, 22, 255))

    return img.resize((tamanho, tamanho), Image.LANCZOS)


def gerar() -> None:
    icon_512 = _desenhar_base(512, com_fundo=True, escala_conteudo=1.0)
    icon_512.save(ICONES_DIR / "icon-512.png")

    icon_192 = _desenhar_base(192, com_fundo=True, escala_conteudo=1.0)
    icon_192.save(ICONES_DIR / "icon-192.png")

    icon_maskable = _desenhar_base(512, com_fundo=True, escala_conteudo=0.62)
    icon_maskable.save(ICONES_DIR / "icon-maskable-512.png")

    # favicon.ico (aba do navegador) e icone da janela desktop, em varios tamanhos
    tamanhos_ico = [16, 32, 48, 256]
    imgs_ico = [_desenhar_base(t, com_fundo=True, escala_conteudo=1.0) for t in tamanhos_ico]
    imgs_ico[0].save(
        RAIZ / "app" / "static" / "favicon.ico",
        format="ICO",
        sizes=[(t, t) for t in tamanhos_ico],
        append_images=imgs_ico[1:],
    )
    imgs_ico[0].save(
        RAIZ / "icone_app.ico",
        format="ICO",
        sizes=[(t, t) for t in tamanhos_ico],
        append_images=imgs_ico[1:],
    )

    print("Icones gerados em", ICONES_DIR)


if __name__ == "__main__":
    gerar()
