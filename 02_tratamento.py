"""
02_tratamento.py — Transforma os JSONs brutos do TSE em tabelas analíticas (data/processed/).

Saídas:
  candidatos.csv         resultado nacional por candidato
  resultado_longo.csv    votos por candidato em cada nível (BR, UF, município, cidade no exterior)
  ufs.csv                uma linha por UF (+ exterior), com comparecimento e % dos principais candidatos
  municipios.csv         uma linha por município brasileiro, com código IBGE, região, 2022 e variações
  exterior_cidades.csv   uma linha por cidade no exterior, com país e continente
  exterior_paises.csv    agregado por país
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

from exterior_paises import CIDADES, PAISES

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
OUT = RAIZ / "data" / "processed"

# Candidatos destacados; os demais viram "Outros"
PRINCIPAIS = {"22": "flavio", "13": "lula", "70": "cury", "14": "renan", "55": "caiado"}
REGIOES = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}


def num(x) -> int:
    return int(x) if x not in (None, "") else 0


def ler(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def extrair(arquivo: dict) -> tuple[dict, list[dict]]:
    """Separa um JSON de resultado do TSE em (resumo de comparecimento, lista de votos por candidato)."""
    e, v = arquivo["e"], arquivo["v"]
    resumo = {
        "eleitores": num(e["te"]),
        "comparecimento": num(e["c"]),
        "abstencao": num(e["a"]),
        "validos": num(v["vv"]),
        "brancos": num(v["vb"]),
        "nulos": num(v["tvn"]),
    }
    votos = []
    for agr in arquivo["carg"][0]["agr"]:
        for par in agr["par"]:
            for c in par["cand"]:
                votos.append({"numero": c["n"], "candidato": c["nmu"], "partido": par["sg"], "votos": num(c["vap"])})
    return resumo, votos


def linha_wide(resumo: dict, votos: list[dict]) -> dict:
    """Uma linha 'larga': comparecimento + votos e % dos principais candidatos + vencedor."""
    linha = dict(resumo)
    validos = resumo["validos"] or 1
    outros = 0
    for v in votos:
        chave = PRINCIPAIS.get(v["numero"])
        if chave:
            linha[f"v_{chave}"] = v["votos"]
        else:
            outros += v["votos"]
    linha["v_outros"] = outros
    for chave in list(PRINCIPAIS.values()) + ["outros"]:
        linha[f"p_{chave}"] = round(100 * linha.get(f"v_{chave}", 0) / validos, 3)
    venc = max(votos, key=lambda v: v["votos"]) if votos else None
    linha["vencedor"] = venc["candidato"] if venc and venc["votos"] > 0 else None
    linha["vencedor_num"] = venc["numero"] if venc and venc["votos"] > 0 else None
    linha["p_abstencao"] = round(100 * resumo["abstencao"] / (resumo["eleitores"] or 1), 3)
    linha["p_brancos_nulos"] = round(100 * (resumo["brancos"] + resumo["nulos"]) / (resumo["comparecimento"] or 1), 3)
    linha["margem_flavio_lula"] = round(linha["p_flavio"] - linha["p_lula"], 3)
    return linha


def carregar_2022() -> pd.DataFrame:
    """Votos válidos do 1º turno presidencial de 2022 por município TSE (inclui exterior, UF 'ZZ')."""
    cache = OUT / "pres2022_municipios.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"cod_tse": str})
    with zipfile.ZipFile(RAW / "votacao_candidato_munzona_2022.zip") as z:
        df = pd.read_csv(
            z.open("votacao_candidato_munzona_2022_BR.csv"), sep=";", encoding="latin1",
            usecols=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS"],
        )
    df = df[df.NR_TURNO == 1]
    df["cod_tse"] = df.CD_MUNICIPIO.astype(str).str.zfill(5)
    tot = df.groupby("cod_tse").QT_VOTOS_NOMINAIS_VALIDOS.sum().rename("validos22")
    piv = df.pivot_table(index="cod_tse", columns="NR_CANDIDATO", values="QT_VOTOS_NOMINAIS_VALIDOS", aggfunc="sum").fillna(0)
    res = pd.DataFrame({"validos22": tot, "v_lula22": piv[13], "v_bolsonaro22": piv[22]})
    res["uf22"] = df.groupby("cod_tse").SG_UF.first()
    res = res.reset_index()
    res.to_csv(cache, index=False)
    return res


def carregar_abstencao_2022() -> pd.DataFrame:
    """Eleitores aptos e abstenções do 1º turno presidencial de 2022 por município TSE (inclui exterior)."""
    cache = OUT / "abst2022_municipios.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"cod_tse": str})
    with zipfile.ZipFile(RAW / "detalhe_votacao_munzona_2022.zip") as z:
        df = pd.read_csv(
            z.open("detalhe_votacao_munzona_2022_BR.csv"), sep=";", encoding="latin1",
            usecols=["NR_TURNO", "CD_CARGO", "CD_MUNICIPIO", "QT_APTOS", "QT_ABSTENCOES"],
        )
    df = df[(df.NR_TURNO == 1) & (df.CD_CARGO == 1)]
    df["cod_tse"] = df.CD_MUNICIPIO.astype(str).str.zfill(5)
    res = df.groupby("cod_tse", as_index=False).agg(aptos22=("QT_APTOS", "sum"), abst22=("QT_ABSTENCOES", "sum"))
    res.to_csv(cache, index=False)
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = ler(RAW / "tse" / "municipios.json")["abr"]

    # --- Nacional
    resumo_br, votos_br = extrair(ler(RAW / "tse" / "br.json"))
    cand = pd.DataFrame(votos_br)
    cand["pct_validos"] = 100 * cand.votos / resumo_br["validos"]
    cand = cand.sort_values("votos", ascending=False)
    cand.to_csv(OUT / "candidatos.csv", index=False)
    (OUT / "brasil_resumo.json").write_text(json.dumps(linha_wide(resumo_br, votos_br), ensure_ascii=False, indent=1), encoding="utf-8")

    longo, ufs, muns = [], [], []
    for uf in cfg:
        sg = uf["cd"]
        r, vs = extrair(ler(RAW / "tse" / "uf" / f"{sg}.json"))
        ufs.append({"uf": sg.upper(), "nome": uf["ds"].title(), **linha_wide(r, vs)})
        longo += [{"nivel": "UF", "uf": sg.upper(), "cod_tse": sg.upper(), "cod_ibge": None, "nome": uf["ds"], **v} for v in vs]
        for mu in uf["mu"]:
            r, vs = extrair(ler(RAW / "tse" / "mun" / sg / f"{mu['cd']}.json"))
            nivel = "Exterior" if sg == "zz" else "Município"
            muns.append({"uf": sg.upper(), "cod_tse": mu["cd"], "cod_ibge": mu["cdi"] or None, "nome": mu["nm"], **linha_wide(r, vs)})
            longo += [{"nivel": nivel, "uf": sg.upper(), "cod_tse": mu["cd"], "cod_ibge": mu["cdi"] or None, "nome": mu["nm"], **v} for v in vs]

    pd.DataFrame(longo).to_csv(OUT / "resultado_longo.csv", index=False)
    muns = pd.DataFrame(muns)

    # --- Comparação com 2022 (% dos votos válidos)
    p22 = carregar_2022()
    muns = muns.merge(p22.drop(columns="uf22"), on="cod_tse", how="left")
    muns["p_lula22"] = (100 * muns.v_lula22 / muns.validos22).round(3)
    muns["p_bolsonaro22"] = (100 * muns.v_bolsonaro22 / muns.validos22).round(3)
    muns["d_lula"] = (muns.p_lula - muns.p_lula22).round(3)            # Lula 2026 - Lula 2022
    muns["d_bolsonarismo"] = (muns.p_flavio - muns.p_bolsonaro22).round(3)  # Flávio 2026 - Jair 2022

    # Abstenção de 2022 (% dos aptos)
    muns = muns.merge(carregar_abstencao_2022(), on="cod_tse", how="left")
    muns["p_abstencao22"] = (100 * muns.abst22 / muns.aptos22).round(3)
    muns["d_abstencao"] = (muns.p_abstencao - muns.p_abstencao22).round(3)

    # UFs: agrega 2022 por UF
    ufs = pd.DataFrame(ufs)
    agg22 = muns.groupby("uf")[["validos22", "v_lula22", "v_bolsonaro22", "aptos22", "abst22"]].sum()
    ufs = ufs.merge(agg22, left_on="uf", right_index=True, how="left")
    ufs["p_lula22"] = (100 * ufs.v_lula22 / ufs.validos22).round(3)
    ufs["p_bolsonaro22"] = (100 * ufs.v_bolsonaro22 / ufs.validos22).round(3)
    ufs["d_lula"] = (ufs.p_lula - ufs.p_lula22).round(3)
    ufs["d_bolsonarismo"] = (ufs.p_flavio - ufs.p_bolsonaro22).round(3)
    ufs["p_abstencao22"] = (100 * ufs.abst22 / ufs.aptos22).round(3)
    ufs["d_abstencao"] = (ufs.p_abstencao - ufs.p_abstencao22).round(3)
    ibge_uf = {"RO": "N", "AC": "N", "AM": "N", "RR": "N", "PA": "N", "AP": "N", "TO": "N",
               "MA": "NE", "PI": "NE", "CE": "NE", "RN": "NE", "PB": "NE", "PE": "NE", "AL": "NE", "SE": "NE", "BA": "NE",
               "MG": "SE", "ES": "SE", "RJ": "SE", "SP": "SE", "PR": "S", "SC": "S", "RS": "S",
               "MS": "CO", "MT": "CO", "GO": "CO", "DF": "CO", "ZZ": None}
    ufs["regiao"] = ufs.uf.map(ibge_uf).map(REGIOES).fillna("Exterior")
    ufs.to_csv(OUT / "ufs.csv", index=False)

    # --- Municípios brasileiros: região, meso/microrregião e região imediata (IBGE)
    br = muns[muns.uf != "ZZ"].copy()
    ibge = ler(RAW / "geo" / "ibge_municipios.json")
    # Municípios criados recentemente não têm micro/mesorregião (divisão antiga); usamos a região imediata.
    meta = pd.DataFrame([{
        "cod_ibge": str(m["id"]),
        "regiao": m["regiao-imediata"]["regiao-intermediaria"]["UF"]["regiao"]["nome"],
        "mesorregiao": (m["microrregiao"] or {}).get("mesorregiao", {}).get("nome"),
        "microrregiao": (m["microrregiao"] or {}).get("nome"),
        "regiao_imediata": m["regiao-imediata"]["nome"],
        "nome_ibge": m["nome"],
    } for m in ibge])
    br = br.merge(meta, on="cod_ibge", how="left")
    # Municípios novos sem mesorregião: usa a mesorregião predominante na sua região imediata
    meso_imediata = br.dropna(subset=["mesorregiao"]).groupby("regiao_imediata").mesorregiao.agg(lambda x: x.mode().iloc[0])
    br["mesorregiao"] = br.mesorregiao.fillna(br.regiao_imediata.map(meso_imediata))
    br.to_csv(OUT / "municipios.csv", index=False)

    # --- Exterior: cidade -> país -> continente
    ext = muns[muns.uf == "ZZ"].drop(columns=["cod_ibge"]).copy()
    ext["iso3"] = ext.nome.map(CIDADES)
    ext["pais"] = ext.iso3.map(lambda i: PAISES[i][0])
    ext["continente"] = ext.iso3.map(lambda i: PAISES[i][1])
    ext.to_csv(OUT / "exterior_cidades.csv", index=False)

    soma = ["eleitores", "comparecimento", "abstencao", "validos", "brancos", "nulos",
            "v_flavio", "v_lula", "v_cury", "v_renan", "v_caiado", "v_outros", "validos22", "v_lula22", "v_bolsonaro22",
            "aptos22", "abst22"]
    paises = ext.groupby(["iso3", "pais", "continente"], as_index=False)[soma].sum()
    paises["cidades"] = ext.groupby("iso3").size().reindex(paises.iso3).values
    for c in ["flavio", "lula", "cury", "renan", "caiado", "outros"]:
        paises[f"p_{c}"] = (100 * paises[f"v_{c}"] / paises.validos.where(paises.validos > 0)).round(3)
    paises["p_abstencao"] = (100 * paises.abstencao / paises.eleitores).round(3)
    paises["p_lula22"] = (100 * paises.v_lula22 / paises.validos22.where(paises.validos22 > 0)).round(3)
    paises["p_bolsonaro22"] = (100 * paises.v_bolsonaro22 / paises.validos22.where(paises.validos22 > 0)).round(3)
    paises["p_abstencao22"] = (100 * paises.abst22 / paises.aptos22.where(paises.aptos22 > 0)).round(3)
    paises.sort_values("eleitores", ascending=False).to_csv(OUT / "exterior_paises.csv", index=False)

    # --- Checagens de consistência
    print("Checagens:")
    print(f"  Válidos BR (TSE): {resumo_br['validos']:,} | soma UFs: {ufs.validos.sum():,} | soma municípios+exterior: {muns.validos.sum():,}")
    print(f"  Municípios BR: {len(br)} | sem código IBGE: {br.cod_ibge.isna().sum()} | sem meta IBGE: {br.regiao.isna().sum()}")
    print(f"  Municípios sem dado 2022: {br.validos22.isna().sum()} | cidades exterior sem 2022: {ext.validos22.isna().sum()}")
    print(f"  Exterior: {len(ext)} cidades, {len(paises)} países, sem país: {ext.iso3.isna().sum()}")
    a22 = carregar_abstencao_2022()
    print(f"  Abstenção 2022: geral {100 * a22.abst22.sum() / a22.aptos22.sum():.2f}% "
          f"| soma UFs {100 * ufs.abst22.sum() / ufs.aptos22.sum():.2f}% "
          f"| municípios BR sem dado: {br.aptos22.isna().sum()}")


if __name__ == "__main__":
    main()
