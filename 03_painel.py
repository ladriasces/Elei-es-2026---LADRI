"""
03_painel.py — Gera painel/index.html a partir de painel/template.html, embutindo os dados
processados e as malhas geográficas simplificadas (para o painel abrir rápido no navegador).
"""
from __future__ import annotations

import argparse
import base64
import json

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient

from tse_comum import GOATCOUNTER, RAIZ, RAW, carregar_2022, carregar_abstencao_2022, pasta_saida, pasta_tse

PAINEL = RAIZ / "painel"

# Países pequenos demais para o mapa-múndi em baixa resolução: centroides manuais (lon, lat)
CENTROIDES_EXTRAS = {
    "BHR": (50.55, 26.07), "SGP": (103.82, 1.35), "BRB": (-59.54, 13.19), "LCA": (-60.98, 13.91),
    "ATG": (-61.80, 17.07), "STP": (6.61, 0.19), "CPV": (-23.51, 14.93), "GUF": (-53.13, 3.93),
}


def sentido_d3(g):
    """O D3 (geometria esférica) espera o anel externo no sentido horário.
    Pedaços sem área (ilhas que colapsaram na simplificação) são descartados: o D3 os
    interpretaria como o globo inteiro."""
    partes = [g] if isinstance(g, Polygon) else list(g.geoms) if isinstance(g, MultiPolygon) else []
    partes = [orient(p, sign=-1.0) for p in partes if p.area > 0]
    if not partes:
        return g
    return partes[0] if len(partes) == 1 else MultiPolygon(partes)


def geo_compacto(gdf: gpd.GeoDataFrame, tolerancia: float, casas: int = 3) -> dict:
    gdf = gdf.copy()
    # Simplifica, arredonda na grade final (remove o que colapsar) e só então orienta
    simpl = shapely.set_precision(gdf.geometry.simplify(tolerancia, preserve_topology=True).values, 10 ** -casas)
    gdf["geometry"] = gpd.GeoSeries(simpl, index=gdf.index, crs=gdf.crs).map(sentido_d3)
    gj = json.loads(gdf.to_json(drop_id=True))

    def arred(c):
        return [arred(x) for x in c] if isinstance(c[0], list) else [round(c[0], casas), round(c[1], casas)]

    for f in gj["features"]:
        f["geometry"]["coordinates"] = arred(f["geometry"]["coordinates"])
    return gj


def nome_uf(nome: str) -> str:
    """'Mato Grosso Do Sul' -> 'Mato Grosso do Sul' (preposições em minúscula)."""
    for p in ("Do", "De", "Da", "Dos", "Das"):
        nome = nome.replace(f" {p} ", f" {p.lower()} ")
    return nome


def r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


def n0(x) -> int:
    """Contagem inteira (0 quando o local ainda não tem dados)."""
    return 0 if pd.isna(x) else int(x)


def montar_turno(turno: int) -> dict:
    """Dados de um turno no formato que o painel usa (o motor ao vivo do navegador monta o mesmo formato)."""
    OUT = pasta_saida(turno)
    resumo = json.loads((OUT / "brasil_resumo.json").read_text(encoding="utf-8"))
    cand = pd.read_csv(OUT / "candidatos.csv", dtype={"numero": str})
    ufs = pd.read_csv(OUT / "ufs.csv")
    mun = pd.read_csv(OUT / "municipios.csv", dtype={"cod_ibge": str, "cod_tse": str, "vencedor_num": str})
    pa = pd.read_csv(OUT / "exterior_paises.csv")
    cid = pd.read_csv(OUT / "exterior_cidades.csv")

    campos = ["p_flavio", "p_lula", "p_cury", "p_renan", "p_caiado", "p_outros", "p_abstencao", "p_brancos_nulos"]

    p22 = pd.read_csv(OUT / "pres2022_municipios.csv")
    resumo["p_lula22"] = round(100 * p22.v_lula22.sum() / p22.validos22.sum(), 3)
    resumo["p_bolsonaro22"] = round(100 * p22.v_bolsonaro22.sum() / p22.validos22.sum(), 3)
    resumo["mun_flavio"] = int((mun.vencedor_num == "22").sum())
    resumo["mun_lula"] = int((mun.vencedor_num == "13").sum())
    # Contagens com a precisão completa (no navegador os percentuais chegam arredondados)
    resumo["mun_lula_caiu"] = int((mun.d_lula < 0).sum())
    resumo["mun_comparaveis"] = int(mun.d_lula.notna().sum())
    resumo["mun_abst_subiu"] = int((mun.d_abstencao > 0).sum())
    resumo["mun_abst_caiu"] = int((mun.d_abstencao < 0).sum())
    a22 = pd.read_csv(OUT / "abst2022_municipios.csv", dtype={"cod_tse": str})
    resumo["p_abstencao22"] = round(100 * a22.abst22.sum() / a22.aptos22.sum(), 3)
    br22 = ufs[ufs.uf != "ZZ"]
    resumo["p_abstencao22_br"] = round(100 * br22.abst22.sum() / br22.aptos22.sum(), 3)
    status = json.loads((OUT / "status.json").read_text(encoding="utf-8"))

    def venc(v):
        return None if pd.isna(v) else (v if isinstance(v, str) else str(int(v)))

    return {
        "turno": turno,
        "status": status,
        "resumo": resumo,
        "candidatos": [
            {"n": c.numero, "nome": c.candidato.title(), "partido": c.partido, "votos": int(c.votos), "pct": r(c.pct_validos, 2)}
            for c in cand.itertuples()
        ],
        "ufs": [
            {"uf": u.uf, "nome": nome_uf(u.nome), "regiao": u.regiao, "eleitores": int(u.eleitores), "comparecimento": int(u.comparecimento),
             "validos": int(u.validos), "v_flavio": int(u.v_flavio), "v_lula": int(u.v_lula), "v_outros": int(u.validos - u.v_flavio - u.v_lula),
             **{c: r(getattr(u, c)) for c in campos}, "p_lula22": r(u.p_lula22), "p_bolsonaro22": r(u.p_bolsonaro22),
             "aptos22": int(u.aptos22), "abst22": int(u.abst22), "p_abstencao22": r(u.p_abstencao22),
             "validos22": int(u.validos22), "v_lula22": int(u.v_lula22), "v_bolsonaro22": int(u.v_bolsonaro22),
             "venc": venc(u.vencedor_num)}
            for u in ufs.itertuples()
        ],
        # Municípios em formato colunar compacto
        # comparecimento e votos em números absolutos: base das análises ao vivo (comparação nos mesmos locais)
        "mun_cols": ["ibge", "nome", "uf", "eleitores", "validos", *campos, "p_lula22", "p_bolsonaro22", "venc", "meso", "imediata", "p_abstencao22", "aptos22",
                     "comparecimento", "v_flavio", "v_lula"],
        "mun": [
            [m.cod_ibge, m.nome_ibge, m.uf, int(m.eleitores), int(m.validos), *[r(getattr(m, c)) for c in campos],
             r(m.p_lula22), r(m.p_bolsonaro22), venc(m.vencedor_num),
             m.mesorregiao if isinstance(m.mesorregiao, str) else None, m.regiao_imediata,
             r(m.p_abstencao22), None if pd.isna(m.aptos22) else int(m.aptos22),
             n0(m.comparecimento), n0(m.v_flavio), n0(m.v_lula)]
            for m in mun.itertuples()
        ],
        "paises": [
            {"iso3": p.iso3, "pais": p.pais, "continente": p.continente, "cidades": int(p.cidades), "eleitores": int(p.eleitores),
             "comparecimento": int(p.comparecimento), "validos": int(p.validos), "v_flavio": int(p.v_flavio), "v_lula": int(p.v_lula),
             "p_flavio": r(p.p_flavio), "p_lula": r(p.p_lula), "p_abstencao": r(p.p_abstencao),
             "p_lula22": r(p.p_lula22), "p_bolsonaro22": r(p.p_bolsonaro22),
             "p_abstencao22": r(p.p_abstencao22)}
            for p in pa.itertuples()
        ],
        "cidades_ext": [
            {"cidade": c.nome.title(), "pais": c.pais, "eleitores": int(c.eleitores), "comparecimento": int(c.comparecimento),
             "p_flavio": r(c.p_flavio), "p_lula": r(c.p_lula)}
            for c in cid.sort_values("eleitores", ascending=False, kind="stable").itertuples()
        ],
    }


def base_ao_vivo() -> dict:
    """Referências fixas para o motor ao vivo do 2º turno montar, no navegador, os mesmos dados de montar_turno(2)."""
    mun = pd.read_csv(pasta_saida(1) / "municipios.csv", dtype={"cod_ibge": str, "cod_tse": str})
    cid = pd.read_csv(pasta_saida(1) / "exterior_cidades.csv", dtype={"cod_tse": str})
    cache = pasta_saida(2)
    p22 = carregar_2022(2, cache / "pres2022_municipios.csv")
    a22 = carregar_abstencao_2022(2, cache / "abst2022_municipios.csv")
    ref = p22.drop(columns="uf22").merge(a22, on="cod_tse", how="outer")
    ref22 = {t.cod_tse: [None if pd.isna(x) else int(x) for x in (t.validos22, t.v_lula22, t.v_bolsonaro22, t.aptos22, t.abst22)]
             for t in ref.itertuples()}
    cfg = json.loads((pasta_tse(1) / "municipios.json").read_text(encoding="utf-8"))["abr"]
    return {
        "eleicao": "6258",
        "ufs_cfg": [[uf["cd"], uf["ds"], [m["cd"] for m in uf["mu"]]] for uf in cfg],
        "mun_tse": dict(zip(mun.cod_tse, mun.cod_ibge)),
        "ext": [[c.cod_tse, c.nome.title(), c.iso3, c.pais, c.continente] for c in cid.itertuples()],
        "ref22": ref22,
    }


def main(forcar_2t: bool = False) -> None:
    dados = {"t1": montar_turno(1), "t2": None}
    st2 = pasta_saida(2) / "status.json"
    if st2.exists():
        status2 = json.loads(st2.read_text(encoding="utf-8"))
        if status2["final"] or forcar_2t:
            dados["t2"] = montar_turno(2)
            print(f"2º turno embutido (apuração {status2['pst']}%, final: {status2['final']})")
    if dados["t2"] is None:
        print("2º turno ainda não consolidado: o painel acompanha a apuração ao vivo pela API do TSE.")
    dados["base"] = base_ao_vivo()
    mun = pd.read_csv(pasta_saida(1) / "municipios.csv", dtype={"cod_ibge": str})

    # --- Geometrias
    uf_geo = gpd.read_file(RAW / "geo" / "br_uf.geojson")
    siglas = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN",
              25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC",
              43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF"}
    uf_geo["id"] = uf_geo.codarea.astype(int).map(siglas)
    mun_geo = gpd.read_file(RAW / "geo" / "br_municipios.geojson").rename(columns={"codarea": "id"})
    # Contornos das mesorregiões (dissolvendo os municípios), para destacar no mapa por estado
    meso_geo = mun_geo.merge(mun[["cod_ibge", "uf", "mesorregiao"]], left_on="id", right_on="cod_ibge")
    meso_geo = meso_geo[meso_geo.id != "2605459"]  # Fernando de Noronha fica fora do mapa estadual (distorce a escala)
    meso_geo = meso_geo.dissolve(by=["uf", "mesorregiao"]).reset_index()
    meso_geo["id"] = meso_geo.uf + "|" + meso_geo.mesorregiao
    mundo = gpd.read_file(RAW / "geo" / "mundo.geojson")[["ADM0_A3", "geometry"]].rename(columns={"ADM0_A3": "id"})
    mundo = mundo[mundo.id != "ATA"]  # sem Antártida

    # Centroides dos países com eleitores brasileiros (para o mapa de bolhas)
    cent = {}
    for row in mundo.itertuples():
        # usa o maior polígono, para que EUA/França/Rússia caiam no território principal
        g = max(row.geometry.geoms, key=lambda p: p.area) if row.geometry.geom_type == "MultiPolygon" else row.geometry
        pt = g.representative_point()
        cent[row.id] = (round(pt.x, 2), round(pt.y, 2))
    aliases = {"PSE": "PSX", "SSD": "SDS"}
    lonlat = {iso: CENTROIDES_EXTRAS.get(iso) or cent.get(aliases.get(iso, iso)) for iso in {c[2] for c in dados["base"]["ext"]}}
    print("Países sem centroide:", [i for i, v in lonlat.items() if not v])
    dados["base"]["lonlat"] = lonlat
    for t in ("t1", "t2"):
        if dados[t]:
            for pais in dados[t]["paises"]:
                pais["lonlat"] = lonlat.get(pais["iso3"])

    dados["geo"] = {
        "uf": geo_compacto(uf_geo[["id", "geometry"]], 0.02),
        "mun": geo_compacto(mun_geo[["id", "geometry"]], 0.006),
        "meso": geo_compacto(meso_geo[["id", "geometry"]], 0.01),
        "mundo": geo_compacto(mundo, 0.1, 2),
    }

    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    logo = base64.b64encode((PAINEL / "logo_ladri.png").read_bytes()).decode("ascii")
    html = (PAINEL / "template.html").read_text(encoding="utf-8").replace("/*__DADOS__*/null", texto)         .replace("__LOGO__", f"data:image/png;base64,{logo}")
    (PAINEL / "index.html").write_text(html, encoding="utf-8")
    print(f"painel/index.html gerado: {len(html.encode('utf-8')) / 1e6:.2f} MB "
          f"(dados {len(texto.encode('utf-8')) / 1e6:.2f} MB)")
    for k in ("t1", "t2", "base"):
        if dados[k]:
            print(f"  {k}: {len(json.dumps(dados[k], separators=(',', ':'))) / 1e6:.2f} MB")
    site_github(html)


def site_github(html: str) -> None:
    """Versão independente do painel para o GitHub Pages (docs/index.html), com documento HTML completo."""
    corpo = html.replace('<meta charset="utf-8">\n', "", 1)
    fim_head = corpo.index("</style>") + len("</style>")
    cabeca, resto = corpo[:fim_head], corpo[fim_head:]
    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Painel interativo da eleição presidencial de 2026 (TSE): 1º e 2º turnos, apuração ao vivo, resultados por estado e município, voto no exterior e comparação com 2022. LADRI · ASCES-UNITA.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%231d7a3d'/%3E%3Cpath d='M9 17l5 5 9-11' stroke='white' stroke-width='3.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>[hidden] {{ display: none !important; }} img {{ max-width: 100%; }}</style>
<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
{cabeca}
</head>
<body>
{resto}
</body>
</html>
"""
    docs = RAIZ / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(pagina, encoding="utf-8")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    print("docs/index.html gerado (GitHub Pages)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Gera o painel (painel/index.html e docs/index.html).")
    ap.add_argument("--forcar-2t", action="store_true",
                    help="embute o 2º turno mesmo sem totalização final (teste com o simulador)")
    main(ap.parse_args().forcar_2t)
