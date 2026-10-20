"""
02_tratamento.py — Transforma os JSONs brutos do TSE em tabelas analíticas.

Uso:
  python 02_tratamento.py              # 1º turno -> data/processed/
  python 02_tratamento.py --turno 2    # 2º turno -> data/processed/2t/

Saídas:
  candidatos.csv         resultado nacional por candidato
  resultado_longo.csv    votos por candidato em cada nível (BR, UF, município, cidade no exterior)
  ufs.csv                uma linha por UF (+ exterior), com comparecimento e % dos principais candidatos
  municipios.csv         uma linha por município brasileiro, com código IBGE, região, 2022 e variações
  exterior_cidades.csv   uma linha por cidade no exterior, com país e continente
  exterior_paises.csv    agregado por país
A comparação com 2022 usa o mesmo turno de 2022 (1º com 1º, 2º com 2º).
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from exterior_paises import CIDADES, PAISES
from tse_comum import (RAW, REGIAO_UF, REGIOES, carregar_2022, carregar_abstencao_2022, extrair, ler, linha_wide,
                       pasta_saida, pasta_tse)


def main(turno: int = 1) -> None:
    TSE_DIR = pasta_tse(turno)
    OUT = pasta_saida(turno)
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = ler(TSE_DIR / "municipios.json")["abr"]

    # --- Nacional
    br_json = ler(TSE_DIR / "br.json")
    resumo_br, votos_br = extrair(br_json)
    status = {"turno": turno, "pst": br_json["s"]["pst"], "final": br_json.get("tf") == "s",
              "gerado": f"{br_json.get('dg', '')} {br_json.get('hg', '')}".strip(),
              "totalizado": f"{br_json.get('dt', '')} {br_json.get('ht', '')}".strip()}
    (OUT / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = pd.DataFrame(votos_br)
    cand["pct_validos"] = 100 * cand.votos / (resumo_br["validos"] or 1)
    cand = cand.sort_values("votos", ascending=False)
    cand.to_csv(OUT / "candidatos.csv", index=False)
    (OUT / "brasil_resumo.json").write_text(json.dumps(linha_wide(resumo_br, votos_br), ensure_ascii=False, indent=1), encoding="utf-8")

    longo, ufs, muns = [], [], []
    for uf in cfg:
        sg = uf["cd"]
        r, vs = extrair(ler(TSE_DIR / "uf" / f"{sg}.json"))
        ufs.append({"uf": sg.upper(), "nome": uf["ds"].title(), **linha_wide(r, vs)})
        longo += [{"nivel": "UF", "uf": sg.upper(), "cod_tse": sg.upper(), "cod_ibge": None, "nome": uf["ds"], **v} for v in vs]
        for mu in uf["mu"]:
            r, vs = extrair(ler(TSE_DIR / "mun" / sg / f"{mu['cd']}.json"))
            nivel = "Exterior" if sg == "zz" else "Município"
            muns.append({"uf": sg.upper(), "cod_tse": mu["cd"], "cod_ibge": mu["cdi"] or None, "nome": mu["nm"], **linha_wide(r, vs)})
            longo += [{"nivel": nivel, "uf": sg.upper(), "cod_tse": mu["cd"], "cod_ibge": mu["cdi"] or None, "nome": mu["nm"], **v} for v in vs]

    pd.DataFrame(longo).to_csv(OUT / "resultado_longo.csv", index=False)
    muns = pd.DataFrame(muns)

    # --- Comparação com o mesmo turno de 2022 (% dos votos válidos)
    p22 = carregar_2022(turno, OUT / "pres2022_municipios.csv")
    muns = muns.merge(p22.drop(columns="uf22"), on="cod_tse", how="left")
    muns["p_lula22"] = (100 * muns.v_lula22 / muns.validos22).round(3)
    muns["p_bolsonaro22"] = (100 * muns.v_bolsonaro22 / muns.validos22).round(3)
    muns["d_lula"] = (muns.p_lula - muns.p_lula22).round(3)            # Lula 2026 - Lula 2022
    muns["d_bolsonarismo"] = (muns.p_flavio - muns.p_bolsonaro22).round(3)  # Flávio 2026 - Jair 2022

    # Abstenção de 2022 (% dos aptos)
    a22 = carregar_abstencao_2022(turno, OUT / "abst2022_municipios.csv")
    muns = muns.merge(a22, on="cod_tse", how="left")
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
    ufs["regiao"] = ufs.uf.map(REGIAO_UF).map(REGIOES).fillna("Exterior")
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
    paises.sort_values("eleitores", ascending=False, kind="stable").to_csv(OUT / "exterior_paises.csv", index=False)

    # --- Checagens de consistência
    print(f"Checagens ({turno}º turno):")
    print(f"  Válidos BR (TSE): {resumo_br['validos']:,} | soma UFs: {ufs.validos.sum():,} | soma municípios+exterior: {muns.validos.sum():,}")
    print(f"  Municípios BR: {len(br)} | sem código IBGE: {br.cod_ibge.isna().sum()} | sem meta IBGE: {br.regiao.isna().sum()}")
    print(f"  Municípios sem dado 2022: {br.validos22.isna().sum()} | cidades exterior sem 2022: {ext.validos22.isna().sum()}")
    print(f"  Exterior: {len(ext)} cidades, {len(paises)} países, sem país: {ext.iso3.isna().sum()}")
    print(f"  Abstenção 2022 ({turno}º turno): geral {100 * a22.abst22.sum() / a22.aptos22.sum():.2f}% "
          f"| soma UFs {100 * ufs.abst22.sum() / ufs.aptos22.sum():.2f}% "
          f"| municípios BR sem dado: {br.aptos22.isna().sum()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Tratamento dos resultados presidenciais de 2026 (TSE).")
    ap.add_argument("--turno", type=int, choices=[1, 2], default=1)
    main(ap.parse_args().turno)
