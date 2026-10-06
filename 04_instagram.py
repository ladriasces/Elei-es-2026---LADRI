"""
04_instagram.py — Gera artes quadradas (1:1, 2160 x 2160 px) para o Instagram do LADRI, na pasta instagram/.

Usa as tabelas de data/processed/ e as malhas de data/raw/geo/ (rodar antes 01, 02).
Fontes: Segoe UI (família padrão do Windows), em pesos Black, Semibold e Regular.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
OUT = RAIZ / "instagram"
OUT.mkdir(exist_ok=True)

# ---------- Identidade visual (a mesma do painel)
BG = "#f4f6f4"
INK = "#121714"
INK2 = "#4b524e"
MUTED = "#7f8782"
LINE = "#dde1dd"
ACCENT = "#1d7a3d"
AZUL = "#2a78d6"   # Flávio
VERM = "#e34948"   # Lula
MID = "#eeefec"
ABST = "#5b4a99"
CINZA = "#a6aba7"
UP, DOWN = "#7a3fb8", "#d9741f"

def fonte_sistema(arquivo: str, peso: str) -> fm.FontProperties:
    """Segoe UI no Windows; fora dele, usa a DejaVu Sans que vem com o matplotlib."""
    caminho = Path(r"C:\Windows\Fonts") / arquivo
    return fm.FontProperties(fname=caminho) if caminho.exists() else fm.FontProperties(family="DejaVu Sans", weight=peso)


F_TITULO = fonte_sistema("seguibl.ttf", "heavy")
F_SEMI = fonte_sistema("seguisb.ttf", "semibold")
F_TEXTO = fonte_sistema("segoeui.ttf", "normal")


def fonte(base: fm.FontProperties, tamanho: float) -> fm.FontProperties:
    f = base.copy()
    f.set_size(tamanho)
    return f


LADO = 7.2   # polegadas; 7.2 x 300 dpi = 2160 px
DPI = 300

cm_margem = LinearSegmentedColormap.from_list("margem", ["#a3201f", VERM, "#f3b9b8", MID, "#b4d0f3", AZUL, "#164a8c"])
cm_lula = LinearSegmentedColormap.from_list("lula", [MID, "#f3b9b8", VERM, "#8f1d1c"])
cm_flavio = LinearSegmentedColormap.from_list("flavio", [MID, "#b4d0f3", AZUL, "#123f78"])
cm_abst = LinearSegmentedColormap.from_list("abst", [MID, "#c9c1e8", "#8c7cc9", ABST, "#2f2561"])
cm_var = LinearSegmentedColormap.from_list("var", [DOWN, "#f2c9a3", MID, "#d4bdef", UP])


def br(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pp(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + br(abs(v)) + " p.p."


# ---------- Moldura comum
def moldura(eyebrow: str, titulo: str, subtitulo: str):
    fig = plt.figure(figsize=(LADO, LADO), dpi=DPI, facecolor=BG)
    fig.text(0.06, 0.945, eyebrow.upper(), fontproperties=F_SEMI, fontsize=8.5, color=ACCENT, va="top")
    fig.text(0.06, 0.915, titulo, fontproperties=F_TITULO, fontsize=23, color=INK, va="top", linespacing=1.0)
    fig.text(0.06, 0.835, subtitulo, fontproperties=F_TEXTO, fontsize=9.5, color=INK2, va="top", linespacing=1.35)
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.058, 0.058], color=LINE, lw=0.8))
    fig.text(0.06, 0.038, "Fonte: TSE, 1º turno de 4/10/2026 (100% das seções apuradas)", fontproperties=F_TEXTO, fontsize=7, color=MUTED, va="center")
    fig.text(0.94, 0.038, "LADRI · ASCES-UNITA", fontproperties=F_SEMI, fontsize=7.5, color=INK2, va="center", ha="right")
    return fig


def barra_cor(fig, cmap, vmin, vmax, ticks, rotulos, titulo, y=0.105):
    ax = fig.add_axes([0.25, y, 0.5, 0.016])
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    ax.imshow(grad, aspect="auto", cmap=cmap, extent=[vmin, vmax, 0, 1])
    ax.set_yticks([])
    ax.set_xticks(ticks)
    ax.set_xticklabels(rotulos, fontproperties=F_TEXTO, fontsize=7.5, color=INK2)
    ax.tick_params(length=0, pad=4)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(0.5, y + 0.03, titulo, fontproperties=F_SEMI, fontsize=8, color=INK, ha="center")


def salvar(fig, nome):
    fig.savefig(OUT / nome, dpi=DPI, facecolor=BG)
    plt.close(fig)
    print("  ", nome)


# ---------- Dados
mun = pd.read_csv(PROC / "municipios.csv", dtype={"cod_ibge": str})
ufs = pd.read_csv(PROC / "ufs.csv")
paises = pd.read_csv(PROC / "exterior_paises.csv")
cand = pd.read_csv(PROC / "candidatos.csv", dtype={"numero": str})
pct = dict(zip(cand.numero, cand.pct_validos))
br_res = ufs[ufs.uf != "ZZ"]
tot_el = ufs.eleitores.sum()
p_abst_br = 100 * ufs.abstencao.sum() / tot_el   # abstenção geral (inclui o exterior)
p_abst_nac = 100 * br_res.abstencao.sum() / br_res.eleitores.sum()   # só no Brasil

malha = gpd.read_file(RAW / "geo" / "br_municipios.geojson").rename(columns={"codarea": "cod_ibge"})
geo = malha.merge(mun, on="cod_ibge", how="left")
geo["margem"] = geo.p_flavio - geo.p_lula
geo["d_lula"] = geo.p_lula - geo.p_lula22
uf_geo = gpd.read_file(RAW / "geo" / "br_uf.geojson")


def mapa_br(fig, coluna=None, cmap=None, vmin=None, vmax=None, cores=None):
    ax = fig.add_axes([0.04, 0.15, 0.92, 0.66])
    if cores is not None:
        geo.plot(ax=ax, color=cores, linewidth=0)
    else:
        geo.plot(ax=ax, column=coluna, cmap=cmap, norm=Normalize(vmin, vmax), linewidth=0, missing_kwds={"color": LINE})
    uf_geo.boundary.plot(ax=ax, color="white", linewidth=0.55)
    ax.set_axis_off()
    return ax


def main():
    print("Gerando artes em", OUT)
    f_, l_ = pct["22"], pct["13"]
    n_f = int((mun.vencedor_num == 22).sum())
    n_l = int((mun.vencedor_num == 13).sum())

    # 1) Vencedor por município
    fig = moldura("Eleições 2026 · 1º turno presidencial", "Quem venceu em cada município",
                  f"Flávio Bolsonaro venceu em {br(n_f, 0)} municípios e Lula em {br(n_l, 0)}.\n"
                  f"No total de votos válidos: Flávio {br(f_, 2)}% × Lula {br(l_, 2)}%. Os dois vão ao 2º turno.")
    mapa_br(fig, cores=geo.vencedor_num.map({22: AZUL, 13: VERM}).fillna(LINE))
    fig.legend(handles=[Patch(color=AZUL, label="Flávio Bolsonaro (PL)"), Patch(color=VERM, label="Lula (PT)")],
               loc="center", bbox_to_anchor=(0.5, 0.11), ncol=2, frameon=False, prop=fonte(F_SEMI, 8.5), handlelength=1.2)
    salvar(fig, "01_brasil_vencedor_por_municipio.png")

    # 2) Margem
    fig = moldura("Eleições 2026 · 1º turno presidencial", "A margem em cada município",
                  "Diferença entre o percentual de Flávio Bolsonaro e o de Lula nos votos válidos.\n"
                  "Quanto mais intensa a cor, maior a vantagem do candidato.")
    mapa_br(fig, "margem", cm_margem, -70, 70)
    barra_cor(fig, cm_margem, -70, 70, [-70, -35, 0, 35, 70], ["Lula +70", "+35", "0", "+35", "Flávio +70"], "Vantagem em pontos percentuais")
    salvar(fig, "02_brasil_margem.png")

    # 3) % Lula
    fig = moldura("Eleições 2026 · 1º turno presidencial", "Onde Lula foi mais votado",
                  f"Percentual de Lula (PT) nos votos válidos de cada município.\nNo Brasil: {br(l_, 2)}%. No Nordeste, passou de 60%.")
    mapa_br(fig, "p_lula", cm_lula, 0, 90)
    barra_cor(fig, cm_lula, 0, 90, [0, 30, 60, 90], ["0%", "30%", "60%", "90%"], "Lula, % dos votos válidos")
    salvar(fig, "03_brasil_votos_lula.png")

    # 4) % Flávio
    fig = moldura("Eleições 2026 · 1º turno presidencial", "Onde Flávio Bolsonaro foi mais votado",
                  f"Percentual de Flávio Bolsonaro (PL) nos votos válidos de cada município.\nNo Brasil: {br(f_, 2)}%. No Sul, chegou a 60%.")
    mapa_br(fig, "p_flavio", cm_flavio, 0, 90)
    barra_cor(fig, cm_flavio, 0, 90, [0, 30, 60, 90], ["0%", "30%", "60%", "90%"], "Flávio Bolsonaro, % dos votos válidos")
    salvar(fig, "04_brasil_votos_flavio.png")

    # 5) Abstenção
    fig = moldura("Eleições 2026 · 1º turno presidencial", "Abstenção por município",
                  f"Eleitores aptos que não foram votar. Abstenção geral: {br(p_abst_br)}%, ou {br(ufs.abstencao.sum() / 1e6)} milhões\n"
                  f"de pessoas (inclui o exterior). Só no Brasil, a abstenção foi de {br(p_abst_nac)}%.")
    mapa_br(fig, "p_abstencao", cm_abst, 5, 40)
    barra_cor(fig, cm_abst, 5, 40, [5, 15, 25, 35], ["5%", "15%", "25%", "35%"], "Abstenção, % dos eleitores aptos")
    salvar(fig, "05_brasil_abstencao.png")

    # 6) Exterior
    zz = ufs[ufs.uf == "ZZ"].iloc[0]
    fig = moldura("Eleições 2026 · Brasileiros no exterior", "Como votaram os brasileiros\nque vivem fora do país",
                  "")
    fig.texts[2].set_text(f"{br(zz.eleitores, 0)} eleitores aptos em {len(paises)} países. Lula {br(zz.p_lula)}% × Flávio {br(zz.p_flavio)}%.\n"
                          f"A abstenção foi de {br(zz.p_abstencao)}%, quase o triplo da registrada no Brasil.")
    fig.texts[2].set_y(0.80)
    mundo = gpd.read_file(RAW / "geo" / "mundo.geojson")
    mundo = mundo[mundo.ADM0_A3 != "ATA"].to_crs("+proj=natearth")
    maior = lambda g: max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    pts = mundo[["ADM0_A3", "geometry"]].copy()
    pts["geometry"] = pts.geometry.map(lambda g: maior(g).representative_point())
    b = pts.rename(columns={"ADM0_A3": "iso3"}).merge(paises, on="iso3").sort_values("eleitores", ascending=False)
    b["margem"] = b.p_flavio - b.p_lula
    ax = fig.add_axes([0.03, 0.375, 0.94, 0.37])
    mundo.plot(ax=ax, color="#e3e6e2", edgecolor=BG, linewidth=0.3)
    mundo[mundo.ADM0_A3 == "BRA"].plot(ax=ax, color="#c3c9c4", linewidth=0)
    ax.scatter(b.geometry.x, b.geometry.y, s=b.eleitores / 260, c=b.margem, cmap=cm_margem, norm=Normalize(-70, 70),
               edgecolor="white", linewidth=0.6, zorder=3, alpha=.95)
    ax.set_axis_off()
    ax.set_ylim(-6.3e6, 8.6e6)
    # Ranking dos 8 maiores
    top = paises.head(8)
    axr = fig.add_axes([0.2, 0.1, 0.6, 0.24])
    y = np.arange(len(top))[::-1]
    axr.barh(y, top.p_flavio, color=AZUL, height=0.62)
    axr.barh(y, top.p_lula, left=100 - top.p_lula, color=VERM, height=0.62)
    axr.barh(y, 100 - top.p_flavio - top.p_lula, left=top.p_flavio, color=CINZA, height=0.62)
    for yi, (_, r) in zip(y, top.iterrows()):
        axr.text(-2, yi, r.pais, ha="right", va="center", fontproperties=F_SEMI, fontsize=7.5, color=INK)
        axr.text(2, yi, f"{br(r.p_flavio, 0)}%", ha="left", va="center", fontproperties=F_SEMI, fontsize=6.8, color="white")
        axr.text(98, yi, f"{br(r.p_lula, 0)}%", ha="right", va="center", fontproperties=F_SEMI, fontsize=6.8, color="white")
        axr.text(102, yi, f"{br(r.eleitores / 1000, 0)} mil", ha="left", va="center", fontproperties=F_TEXTO, fontsize=6.8, color=MUTED)
    axr.set_xlim(0, 100)
    axr.set_axis_off()
    fig.text(0.2, 0.355, "Os 8 países com mais eleitores", fontproperties=F_SEMI, fontsize=8, color=INK)
    fig.text(0.8, 0.355, "eleitores aptos →", fontproperties=F_TEXTO, fontsize=6.8, color=MUTED, ha="right")
    fig.legend(handles=[Patch(color=AZUL, label="Flávio"), Patch(color=CINZA, label="Outros"), Patch(color=VERM, label="Lula")],
               loc="center", bbox_to_anchor=(0.5, 0.082), ncol=3, frameon=False, prop=fonte(F_TEXTO, 7.5), handlelength=1)
    fig.text(0.06, 0.40, "Área da bolha proporcional aos eleitores.\nCor: azul, vantagem de Flávio; vermelho, de Lula.",
             fontproperties=F_TEXTO, fontsize=6.5, color=MUTED, ha="left", va="bottom")
    salvar(fig, "06_mundo_brasileiros_no_exterior.png")

    # 7) 2022 × 2026 por estado (halteres)
    d = br_res.copy()
    d["d_lula"] = d.p_lula - d.p_lula22
    d["d_pl"] = d.p_flavio - d.p_bolsonaro22
    d = d.sort_values("d_lula", ascending=False).reset_index(drop=True)
    p22 = pd.read_csv(PROC / "pres2022_municipios.csv")
    l22 = 100 * p22.v_lula22.sum() / p22.validos22.sum()
    b22 = 100 * p22.v_bolsonaro22.sum() / p22.validos22.sum()
    fig = moldura("Eleições 2026 × 2022 · 1º turno", "O que mudou desde 2022",
                  f"Lula: {br(l22)}% → {br(l_)}% ({pp(l_ - l22)}).  PL: Jair {br(b22)}% → Flávio {br(f_)}% ({pp(f_ - b22)}).\n"
                  f"Lula perdeu espaço em {int((d.d_lula < 0).sum())} dos 27 estados; o PL cresceu em {int((d.d_pl > 0).sum())}.")
    y = np.arange(len(d))[::-1]
    for i, (col22, col26, cor, titulo, x0) in enumerate([
        ("p_lula22", "p_lula", VERM, "Lula", 0.17),
        ("p_bolsonaro22", "p_flavio", AZUL, "PL (Jair → Flávio)", 0.57),
    ]):
        ax = fig.add_axes([x0, 0.13, 0.33, 0.585])
        ax.set_facecolor(BG)
        for xv in [20, 40, 60, 80]:
            ax.axvline(xv, color=LINE, lw=0.6, zorder=0)
        ax.hlines(y, d[col22], d[col26], color="#c3c9c4", lw=1.6, zorder=1)
        ax.scatter(d[col22], y, s=16, color=CINZA, zorder=2)
        ax.scatter(d[col26], y, s=22, color=cor, zorder=3, edgecolor="white", linewidth=0.5)
        ax.set_xlim(12, 82)
        ax.set_ylim(-0.8, len(d) - 0.2)
        ax.set_yticks(y)
        ax.set_yticklabels(d.uf if i == 0 else [""] * len(d), fontproperties=F_SEMI, fontsize=6.8, color=INK2)
        ax.set_xticks([20, 40, 60, 80])
        ax.set_xticklabels(["20%", "40%", "60%", "80%"], fontproperties=F_TEXTO, fontsize=6.8, color=MUTED)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        delta = d[col26] - d[col22]
        for yi, v in zip(y, delta):
            ax.text(84, yi, pp(v).replace(" p.p.", ""), va="center", fontproperties=F_TEXTO, fontsize=6.3,
                    color=UP if v > 0 else DOWN, clip_on=False)
        ax.set_title(titulo, loc="left", fontproperties=F_SEMI, fontsize=9, color=INK, pad=8)
    fig.legend(handles=[Patch(color=CINZA, label="2022"), Patch(color=VERM, label="Lula 2026"), Patch(color=AZUL, label="Flávio 2026")],
               loc="center", bbox_to_anchor=(0.5, 0.085), ncol=3, frameon=False, prop=fonte(F_TEXTO, 7.5), handlelength=1)
    fig.text(0.06, 0.755, "Estados ordenados da maior alta à maior queda de Lula; valores em p.p. dos votos válidos.",
             fontproperties=F_TEXTO, fontsize=6.8, color=MUTED)
    salvar(fig, "07_2022_x_2026_por_estado.png")

    # 8) Variação de Lula e do PL por município (dois mapas lado a lado, mesma escala)
    geo["d_pl"] = geo.p_flavio - geo.p_bolsonaro22
    com_dados = int(geo.d_lula.notna().sum())
    fig = moldura("Eleições 2026 × 2022 · 1º turno", "Onde cada lado ganhou\ne perdeu espaço",
                  "")
    fig.texts[2].set_text(f"Variação do percentual nos votos válidos, de 2022 para 2026, por município.\n"
                          f"Lula caiu em {br(int((geo.d_lula < 0).sum()), 0)} e o PL cresceu em {br(int((geo.d_pl > 0).sum()), 0)} "
                          f"dos {br(com_dados, 0)} municípios com dados nos dois anos.")
    fig.texts[2].set_y(0.80)
    for x0, col, titulo, sub in [
        (0.03, "d_lula", "Lula (PT)", f"Brasil: {pp(l_ - l22)}"),
        (0.51, "d_pl", "PL: Jair → Flávio Bolsonaro", f"Brasil: {pp(f_ - b22)}"),
    ]:
        ax = fig.add_axes([x0, 0.165, 0.46, 0.53])
        geo.plot(ax=ax, column=col, cmap=cm_var, norm=Normalize(-15, 15), linewidth=0, missing_kwds={"color": LINE})
        uf_geo.boundary.plot(ax=ax, color="white", linewidth=0.4)
        ax.set_axis_off()
        fig.text(x0 + 0.03, 0.715, titulo, fontproperties=F_SEMI, fontsize=10, color=INK)
        fig.text(x0 + 0.03, 0.697, sub, fontproperties=F_TEXTO, fontsize=7.5, color=INK2)
    barra_cor(fig, cm_var, -15, 15, [-15, -7.5, 0, 7.5, 15], ["−15", "−7,5", "0", "+7,5", "+15"],
              "Variação em pontos percentuais  (laranja: perdeu espaço · roxo: ganhou)")
    salvar(fig, "08_2022_x_2026_mapas_variacao_lula_e_flavio.png")


if __name__ == "__main__":
    main()
