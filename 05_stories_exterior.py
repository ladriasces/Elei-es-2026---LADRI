"""
05_stories_exterior.py — Arte "Brasileiros no exterior" no visual escuro do painel, em dois formatos:
  instagram/09_stories_exterior_9x16.png      (vertical, stories: 2160 x 3840 px)
  instagram/10_exterior_16x9.png              (horizontal: 3840 x 2160 px)
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import FancyBboxPatch, Patch

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
OUT = RAIZ / "instagram"
OUT.mkdir(exist_ok=True)

# Paleta escura do painel
BG = "#0e1110"
SURF = "#161a18"
LINE = "#2a302d"
TERRA = "#262b28"
INK = "#eef1ef"
INK2 = "#bcc3be"
MUTED = "#868d89"
ACCENT = "#3fae63"
AZUL = "#3987e5"
VERM = "#e66767"
MID = "#4a504c"
ABST = "#8f7fd6"
CINZA = "#5f6561"

def fonte_sistema(arquivo: str, peso: str) -> fm.FontProperties:
    """Segoe UI no Windows; fora dele, usa a DejaVu Sans que vem com o matplotlib."""
    caminho = Path(r"C:\Windows\Fonts") / arquivo
    return fm.FontProperties(fname=caminho) if caminho.exists() else fm.FontProperties(family="DejaVu Sans", weight=peso)


F_TITULO = fonte_sistema("seguibl.ttf", "heavy")
F_SEMI = fonte_sistema("seguisb.ttf", "semibold")
F_TEXTO = fonte_sistema("segoeui.ttf", "normal")
DPI = 300

cm_margem = LinearSegmentedColormap.from_list("margem", [VERM, MID, AZUL])


def br(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fonte(base, tamanho):
    f = base.copy()
    f.set_size(tamanho)
    return f


# ---------- Dados
ufs = pd.read_csv(PROC / "ufs.csv")
zz = ufs[ufs.uf == "ZZ"].iloc[0]
paises = pd.read_csv(PROC / "exterior_paises.csv")
p_abst_br = 100 * ufs[ufs.uf != "ZZ"].abstencao.sum() / ufs[ufs.uf != "ZZ"].eleitores.sum()   # só no Brasil
p_abst_geral = 100 * ufs.abstencao.sum() / ufs.eleitores.sum()                               # inclui o exterior

mundo = gpd.read_file(RAW / "geo" / "mundo.geojson")
mundo = mundo[mundo.ADM0_A3 != "ATA"].to_crs("+proj=natearth")
maior = lambda g: max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
pts = mundo[["ADM0_A3", "geometry"]].copy()
pts["geometry"] = pts.geometry.map(lambda g: maior(g).representative_point())
bolhas = pts.rename(columns={"ADM0_A3": "iso3"}).merge(paises, on="iso3").sort_values("eleitores", ascending=False)
bolhas["margem"] = bolhas.p_flavio - bolhas.p_lula

KPIS = [
    ("Eleitores aptos no exterior", br(zz.eleitores, 0), f"em {len(paises)} países", INK),
    ("Compareceram", br(zz.comparecimento, 0), f"{br(100 - zz.p_abstencao)}% dos aptos", INK),
    ("Abstenção", f"{br(zz.p_abstencao)}%", f"no Brasil: {br(p_abst_br)}% · geral: {br(p_abst_geral)}%", ABST),
    ("Lula no exterior", f"{br(zz.p_lula)}%", f"2022: {br(zz.p_lula22)}%", VERM),
    ("Flávio no exterior", f"{br(zz.p_flavio)}%", f"Jair em 2022: {br(zz.p_bolsonaro22)}%", AZUL),
]


def cartao(fig, x, y, w, h, rotulo, valor, sub, cor, escala=1.0):
    fig.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012", transform=fig.transFigure,
                                  facecolor=SURF, edgecolor=LINE, linewidth=0.8))
    fig.text(x + 0.018 * escala, y + h * 0.78, rotulo, fontproperties=fonte(F_TEXTO, 8.5 * escala), color=INK2, va="center")
    fig.text(x + 0.018 * escala, y + h * 0.47, valor, fontproperties=fonte(F_TITULO, 19 * escala), color=cor, va="center")
    fig.text(x + 0.018 * escala, y + h * 0.17, sub, fontproperties=fonte(F_TEXTO, 7.5 * escala), color=MUTED, va="center")


def mapa(ax, escala_bolha):
    mundo.plot(ax=ax, color=TERRA, edgecolor=BG, linewidth=0.3)
    mundo[mundo.ADM0_A3 == "BRA"].plot(ax=ax, color="#363c38", linewidth=0)
    ax.scatter(bolhas.geometry.x, bolhas.geometry.y, s=bolhas.eleitores / escala_bolha, c=bolhas.margem,
               cmap=cm_margem, norm=Normalize(-50, 50), edgecolor=BG, linewidth=0.6, zorder=3, alpha=.95)
    ax.set_ylim(-6.3e6, 8.6e6)
    ax.set_axis_off()


def barra_legenda(fig, x, y, w, tam=1.0):
    ax = fig.add_axes([x, y, w, 0.012 / tam if tam < 1 else 0.012])
    ax.imshow(np.linspace(0, 1, 256).reshape(1, -1), aspect="auto", cmap=cm_margem, extent=[-50, 50, 0, 1])
    ax.set_yticks([])
    ax.set_xticks([-50, 0, 50])
    ax.set_xticklabels(["Lula +50", "0", "Flávio +50"], fontproperties=fonte(F_TEXTO, 7.5 * tam), color=INK2)
    ax.tick_params(length=0, pad=3)
    rot = ax.get_xticklabels()
    rot[0].set_ha("left")
    rot[-1].set_ha("right")
    for s in ax.spines.values():
        s.set_visible(False)
    return ax


def top_paises(fig, rect, n, tam=1.0):
    top = paises.head(n)
    ax = fig.add_axes(rect)
    y = np.arange(len(top))[::-1]
    ax.barh(y, top.p_flavio, color=AZUL, height=0.62)
    ax.barh(y, 100 - top.p_flavio - top.p_lula, left=top.p_flavio, color=CINZA, height=0.62)
    ax.barh(y, top.p_lula, left=100 - top.p_lula, color=VERM, height=0.62)
    for yi, (_, r) in zip(y, top.iterrows()):
        ax.text(-2, yi, r.pais, ha="right", va="center", fontproperties=fonte(F_SEMI, 8 * tam), color=INK)
        ax.text(2, yi, f"{br(r.p_flavio, 0)}%", ha="left", va="center", fontproperties=fonte(F_SEMI, 7 * tam), color="white")
        ax.text(98, yi, f"{br(r.p_lula, 0)}%", ha="right", va="center", fontproperties=fonte(F_SEMI, 7 * tam), color="white")
        ax.text(102, yi, f"{br(r.eleitores / 1000, 0)} mil", ha="left", va="center", fontproperties=fonte(F_TEXTO, 7 * tam), color=MUTED)
    ax.set_xlim(0, 100)
    ax.set_axis_off()


def rodape(fig, y, tam=1.0, m=0.06):
    fig.text(m, y, "Fonte: TSE, 1º turno de 4/10/2026 (100% das seções apuradas)", fontproperties=fonte(F_TEXTO, 7 * tam), color=MUTED, va="center")
    fig.text(1 - m, y, "LADRI · ASCES-UNITA", fontproperties=fonte(F_SEMI, 7.5 * tam), color=INK2, va="center", ha="right")


def vertical():
    """9:16 para stories. Conteúdo dentro da área segura (sem os 13% de cima e de baixo)."""
    fig = plt.figure(figsize=(7.2, 12.8), dpi=DPI, facecolor=BG)
    fig.text(0.06, 0.865, "ELEIÇÕES 2026 · 1º TURNO", fontproperties=fonte(F_SEMI, 10), color=ACCENT, va="top")
    fig.text(0.06, 0.845, "Como votaram os\nbrasileiros no exterior", fontproperties=fonte(F_TITULO, 27), color=INK, va="top", linespacing=1.0)
    # KPIs: 2 em cima, 3 embaixo
    w2, w3, h, g = 0.43, 0.2733, 0.072, 0.02
    y1, y2 = 0.665, 0.583
    for i, k in enumerate(KPIS[:2]):
        cartao(fig, 0.06 + i * (w2 + g), y1, w2, h, *k)
    for i, k in enumerate(KPIS[2:]):
        cartao(fig, 0.06 + i * (w3 + g), y2, w3, h, *k, escala=0.85)
    ax = fig.add_axes([0.0, 0.36, 1.0, 0.21])
    mapa(ax, 380)
    fig.text(0.5, 0.365, "Margem: Flávio − Lula (p.p.)", fontproperties=fonte(F_SEMI, 8), color=INK, ha="center")
    barra_legenda(fig, 0.25, 0.345, 0.5)
    fig.text(0.5, 0.318, "Área da bolha proporcional aos eleitores aptos no país.", fontproperties=fonte(F_TEXTO, 7.5), color=MUTED, ha="center")
    fig.text(0.06, 0.283, "Os 6 países com mais eleitores", fontproperties=fonte(F_SEMI, 10), color=INK)
    top_paises(fig, [0.26, 0.145, 0.56, 0.128], 6, tam=1.15)
    rodape(fig, 0.128)
    fig.savefig(OUT / "09_stories_exterior_9x16.png", dpi=DPI, facecolor=BG)
    plt.close(fig)


def horizontal():
    """16:9, no mesmo arranjo do painel: indicadores em cima, mapa grande embaixo."""
    fig = plt.figure(figsize=(12.8, 7.2), dpi=DPI, facecolor=BG)
    fig.text(0.04, 0.93, "ELEIÇÕES 2026 · 1º TURNO", fontproperties=fonte(F_SEMI, 9), color=ACCENT, va="top")
    fig.text(0.04, 0.9, "Como votaram os brasileiros no exterior", fontproperties=fonte(F_TITULO, 24), color=INK, va="top")
    w, h, g = 0.176, 0.135, 0.0125
    for i, k in enumerate(KPIS):
        cartao(fig, 0.04 + i * (w + g), 0.665, w, h, *k, escala=0.9)
    ax = fig.add_axes([0.03, 0.07, 0.94, 0.57])
    mapa(ax, 230)
    fig.text(0.04, 0.2, "Margem: Flávio − Lula (p.p.)", fontproperties=fonte(F_SEMI, 8), color=INK)
    barra_legenda(fig, 0.04, 0.155, 0.2, tam=0.95)
    fig.text(0.04, 0.115, "Área da bolha proporcional\naos eleitores aptos no país.", fontproperties=fonte(F_TEXTO, 7), color=MUTED, va="top")
    rodape(fig, 0.035, tam=0.95, m=0.04)
    fig.savefig(OUT / "10_exterior_16x9.png", dpi=DPI, facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    vertical()
    horizontal()
    print("ok")
