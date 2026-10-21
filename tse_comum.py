"""
tse_comum.py — Funções e constantes usadas por 01_coleta.py, 02_tratamento.py, 03_painel.py e 06_acessos.py.

Turnos de 2026 (cargo Presidente):
  1º turno: eleição 6257 (4/10/2026)
  2º turno: eleição 6258 (25/10/2026)
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
BASE_TSE = "https://resultados.tse.jus.br/oficial"
ELEICOES = {1: "6257", 2: "6258"}
CARGO = "c0001"  # Presidente
# Contador de acessos do site no GitHub Pages (GoatCounter: anônimo, sem cookies). Relatório: python 06_acessos.py
GOATCOUNTER = "ladri"

# Candidatos destacados; os demais viram "Outros"
PRINCIPAIS = {"22": "flavio", "13": "lula", "70": "cury", "14": "renan", "55": "caiado"}
REGIOES = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}
REGIAO_UF = {"RO": "N", "AC": "N", "AM": "N", "RR": "N", "PA": "N", "AP": "N", "TO": "N",
             "MA": "NE", "PI": "NE", "CE": "NE", "RN": "NE", "PB": "NE", "PE": "NE", "AL": "NE", "SE": "NE", "BA": "NE",
             "MG": "SE", "ES": "SE", "RJ": "SE", "SP": "SE", "PR": "S", "SC": "S", "RS": "S",
             "MS": "CO", "MT": "CO", "GO": "CO", "DF": "CO"}


def pasta_tse(turno: int) -> Path:
    """Arquivos brutos do TSE: data/raw/tse (1º turno) ou data/raw/tse_2t (2º turno)."""
    return RAW / ("tse" if turno == 1 else f"tse_{turno}t")


def pasta_saida(turno: int) -> Path:
    """Tabelas tratadas: data/processed (1º turno) ou data/processed/2t (2º turno)."""
    base = RAIZ / "data" / "processed"
    return base if turno == 1 else base / f"{turno}t"


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
    """Uma linha 'larga': comparecimento + votos e % dos principais candidatos + vencedor.
    Candidatos ausentes (no 2º turno, só há Lula e Flávio) entram com 0 voto."""
    linha = dict(resumo)
    validos = resumo["validos"] or 1
    for chave in PRINCIPAIS.values():
        linha[f"v_{chave}"] = 0
    outros = 0
    for v in votos:
        chave = PRINCIPAIS.get(v["numero"])
        if chave:
            linha[f"v_{chave}"] = v["votos"]
        else:
            outros += v["votos"]
    linha["v_outros"] = outros
    for chave in list(PRINCIPAIS.values()) + ["outros"]:
        linha[f"p_{chave}"] = round(100 * linha[f"v_{chave}"] / validos, 3)
    venc = max(votos, key=lambda v: v["votos"]) if votos else None
    linha["vencedor"] = venc["candidato"] if venc and venc["votos"] > 0 else None
    linha["vencedor_num"] = venc["numero"] if venc and venc["votos"] > 0 else None
    linha["p_abstencao"] = round(100 * resumo["abstencao"] / (resumo["eleitores"] or 1), 3)
    linha["p_brancos_nulos"] = round(100 * (resumo["brancos"] + resumo["nulos"]) / (resumo["comparecimento"] or 1), 3)
    linha["margem_flavio_lula"] = round(linha["p_flavio"] - linha["p_lula"], 3)
    return linha


def carregar_2022(turno: int, cache: Path) -> pd.DataFrame:
    """Votos válidos do turno correspondente de 2022, por município TSE (inclui exterior, UF 'ZZ')."""
    if cache.exists():
        return pd.read_csv(cache, dtype={"cod_tse": str})
    with zipfile.ZipFile(RAW / "votacao_candidato_munzona_2022.zip") as z:
        df = pd.read_csv(
            z.open("votacao_candidato_munzona_2022_BR.csv"), sep=";", encoding="latin1",
            usecols=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS"],
        )
    df = df[df.NR_TURNO == turno]
    df["cod_tse"] = df.CD_MUNICIPIO.astype(str).str.zfill(5)
    tot = df.groupby("cod_tse").QT_VOTOS_NOMINAIS_VALIDOS.sum().rename("validos22")
    piv = df.pivot_table(index="cod_tse", columns="NR_CANDIDATO", values="QT_VOTOS_NOMINAIS_VALIDOS", aggfunc="sum").fillna(0)
    res = pd.DataFrame({"validos22": tot, "v_lula22": piv[13], "v_bolsonaro22": piv[22]})
    res["uf22"] = df.groupby("cod_tse").SG_UF.first()
    res = res.reset_index()
    cache.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(cache, index=False)
    return res


def carregar_abstencao_2022(turno: int, cache: Path) -> pd.DataFrame:
    """Eleitores aptos e abstenções do turno correspondente de 2022, por município TSE (inclui exterior)."""
    if cache.exists():
        return pd.read_csv(cache, dtype={"cod_tse": str})
    with zipfile.ZipFile(RAW / "detalhe_votacao_munzona_2022.zip") as z:
        df = pd.read_csv(
            z.open("detalhe_votacao_munzona_2022_BR.csv"), sep=";", encoding="latin1",
            usecols=["NR_TURNO", "CD_CARGO", "CD_MUNICIPIO", "QT_APTOS", "QT_ABSTENCOES"],
        )
    df = df[(df.NR_TURNO == turno) & (df.CD_CARGO == 1)]
    df["cod_tse"] = df.CD_MUNICIPIO.astype(str).str.zfill(5)
    res = df.groupby("cod_tse", as_index=False).agg(aptos22=("QT_APTOS", "sum"), abst22=("QT_ABSTENCOES", "sum"))
    cache.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(cache, index=False)
    return res
