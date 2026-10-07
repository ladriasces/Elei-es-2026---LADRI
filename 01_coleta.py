"""
01_coleta.py — Coleta dos dados do 1º turno presidencial de 2026 (TSE) e das malhas geográficas.

Fontes:
  - TSE, API pública de divulgação de resultados: https://resultados.tse.jus.br
    Eleição 6257 = "Eleição Ordinária Federal - 2026 1º Turno"; cargo 0001 = Presidente.
  - IBGE, API de malhas territoriais: https://servicodados.ibge.gov.br/api/docs/malhas
  - Natural Earth (mapa-múndi), via GitHub.
  - TSE, Portal de Dados Abertos: votação por município em 2022 (~640 MB), para a comparação com 2022.

Tudo é salvo em data/raw/. Arquivos já baixados não são baixados de novo (cache).
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw"
TSE = "https://resultados.tse.jus.br/oficial/ele2026/6257"
ELEICAO = "e006257"
CARGO = "c0001"  # Presidente

sessao = requests.Session()
sessao.headers["User-Agent"] = "LADRI-ASCES analise academica"


def baixar(url: str, destino: Path, tentativas: int = 4) -> Path:
    """Baixa `url` para `destino`, com cache em disco e novas tentativas em caso de falha."""
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tentativas):
        try:
            r = sessao.get(url, timeout=60)
            r.raise_for_status()
            destino.write_bytes(r.content)
            return destino
        except requests.RequestException as erro:
            if i == tentativas - 1:
                raise RuntimeError(f"Falha ao baixar {url}: {erro}") from erro
            time.sleep(2 * (i + 1))
    return destino


def ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def coletar_tse() -> None:
    # 1) Configuração: lista de UFs e municípios (com código TSE e código IBGE)
    cfg = baixar(f"{TSE}/config/mun-{ELEICAO}-cm.json", RAW / "tse" / "municipios.json")
    abrangencias = ler_json(cfg)["abr"]

    # 2) Resultado nacional, por UF e abrangência (comparecimento por UF)
    tarefas = [
        (f"{TSE}/dados/br/br-{CARGO}-{ELEICAO}-u.json", RAW / "tse" / "br.json"),
        (f"{TSE}/dados/br/br-{ELEICAO}-ab.json", RAW / "tse" / "br-abrangencia.json"),
    ]
    for uf in abrangencias:
        sg = uf["cd"]
        tarefas.append((f"{TSE}/dados/{sg}/{sg}-{CARGO}-{ELEICAO}-u.json", RAW / "tse" / "uf" / f"{sg}.json"))
        # 3) Resultado de cada município (e de cada cidade no exterior, UF "zz")
        for mu in uf["mu"]:
            tarefas.append(
                (
                    f"{TSE}/dados/{sg}/{sg}{mu['cd']}-{CARGO}-{ELEICAO}-u.json",
                    RAW / "tse" / "mun" / sg / f"{mu['cd']}.json",
                )
            )

    print(f"TSE: {len(tarefas)} arquivos a verificar/baixar...")
    falhas = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = {pool.submit(baixar, url, dest): url for url, dest in tarefas}
        for n, fut in enumerate(as_completed(futuros), 1):
            try:
                fut.result()
            except Exception as erro:  # noqa: BLE001
                falhas.append(str(erro))
            if n % 500 == 0:
                print(f"  {n}/{len(tarefas)}")
    print(f"TSE concluído. Falhas: {len(falhas)}")
    for f in falhas[:10]:
        print("  ", f)


def coletar_malhas() -> None:
    ibge = "https://servicodados.ibge.gov.br/api/v3/malhas"
    geo = "formato=application/vnd.geo+json"
    baixar(f"{ibge}/paises/BR?intrarregiao=UF&qualidade=minima&{geo}", RAW / "geo" / "br_uf.geojson")
    baixar(f"{ibge}/paises/BR?intrarregiao=municipio&qualidade=minima&{geo}", RAW / "geo" / "br_municipios.geojson")
    baixar(f"{ibge}/estados/PE?intrarregiao=municipio&qualidade=intermediaria&{geo}", RAW / "geo" / "pe_municipios.geojson")
    # Metadados dos municípios (nome, UF, região, mesorregião) — útil para recortes regionais
    baixar("https://servicodados.ibge.gov.br/api/v1/localidades/municipios", RAW / "geo" / "ibge_municipios.json")
    baixar(
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
        RAW / "geo" / "mundo.geojson",
    )
    print("Malhas concluídas.")


def coletar_2022() -> None:
    """Baixa (em partes, sem carregar tudo na memória) o arquivo de votação de 2022 do TSE."""
    destino = RAW / "votacao_candidato_munzona_2022.zip"
    if destino.exists() and destino.stat().st_size > 0:
        return
    url = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip"
    print("Baixando resultados de 2022 (~640 MB)...")
    parcial = destino.with_suffix(".parcial")
    with sessao.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(parcial, "wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
    parcial.replace(destino)
    print("2022 concluído.")


def coletar_abstencao_2022() -> None:
    """Comparecimento e abstenção de 2022 por município e zona (TSE, ~4 MB)."""
    baixar(
        "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip",
        RAW / "detalhe_votacao_munzona_2022.zip",
    )
    print("Abstenção 2022 concluída.")


if __name__ == "__main__":
    coletar_tse()
    coletar_malhas()
    coletar_2022()
    coletar_abstencao_2022()
