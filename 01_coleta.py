"""
01_coleta.py — Coleta dos resultados presidenciais de 2026 (TSE) e das malhas geográficas.

Uso:
  python 01_coleta.py                         # 1º turno (eleição 6257) -> data/raw/tse/
  python 01_coleta.py --turno 2 --atualizar   # 2º turno (eleição 6258) -> data/raw/tse_2t/, baixando tudo de novo
  python 01_coleta.py --turno 2 --base http://localhost:8767   # usa o simulador local da apuração

Fontes:
  - TSE, API pública de divulgação de resultados: https://resultados.tse.jus.br
    Eleição 6257 = 1º turno e 6258 = 2º turno ("Eleição Ordinária Federal - 2026"); cargo 0001 = Presidente.
  - IBGE, API de malhas territoriais: https://servicodados.ibge.gov.br/api/docs/malhas
  - Natural Earth (mapa-múndi), via GitHub.
  - TSE, Portal de Dados Abertos: votação por município em 2022 (~640 MB), para a comparação com 2022.

Tudo é salvo em data/raw/. Arquivos já baixados não são baixados de novo (cache).
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from tse_comum import BASE_TSE, CARGO, ELEICOES, RAW, pasta_tse

sessao = requests.Session()
sessao.headers["User-Agent"] = "LADRI-ASCES analise academica"


def baixar(url: str, destino: Path, tentativas: int = 4, atualizar: bool = False) -> Path:
    """Baixa `url` para `destino`, com cache em disco e novas tentativas em caso de falha.
    Com `atualizar=True`, baixa de novo mesmo que o arquivo já exista (resultados em apuração)."""
    if not atualizar and destino.exists() and destino.stat().st_size > 0:
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


def coletar_tse(turno: int = 1, base: str = BASE_TSE, atualizar: bool = False) -> None:
    cod = ELEICOES[turno]
    TSE = f"{base}/ele2026/{cod}"
    ELEICAO = f"e{int(cod):06d}"
    DEST = pasta_tse(turno)
    # 1) Configuração: lista de UFs e municípios (com código TSE e código IBGE)
    cfg = baixar(f"{TSE}/config/mun-{ELEICAO}-cm.json", DEST / "municipios.json", atualizar=atualizar)
    abrangencias = ler_json(cfg)["abr"]

    # 2) Resultado nacional, por UF e abrangência (comparecimento por UF)
    tarefas = [
        (f"{TSE}/dados/br/br-{CARGO}-{ELEICAO}-u.json", DEST / "br.json"),
        (f"{TSE}/dados/br/br-{ELEICAO}-ab.json", DEST / "br-abrangencia.json"),
    ]
    for uf in abrangencias:
        sg = uf["cd"]
        tarefas.append((f"{TSE}/dados/{sg}/{sg}-{CARGO}-{ELEICAO}-u.json", DEST / "uf" / f"{sg}.json"))
        # 3) Resultado de cada município (e de cada cidade no exterior, UF "zz")
        for mu in uf["mu"]:
            tarefas.append(
                (
                    f"{TSE}/dados/{sg}/{sg}{mu['cd']}-{CARGO}-{ELEICAO}-u.json",
                    DEST / "mun" / sg / f"{mu['cd']}.json",
                )
            )

    print(f"TSE: {len(tarefas)} arquivos a verificar/baixar...")
    falhas = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = {pool.submit(baixar, url, dest, 4, atualizar): url for url, dest in tarefas}
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
    br = ler_json(DEST / "br.json")
    print(f"  Seções totalizadas: {br['s']['pst']}% | totalização final: {'sim' if br.get('tf') == 's' else 'não'}")


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
    ap = argparse.ArgumentParser(description="Coleta dos resultados presidenciais de 2026 (TSE) e malhas.")
    ap.add_argument("--turno", type=int, choices=[1, 2], default=1)
    ap.add_argument("--base", default=BASE_TSE, help="endereço base da API (padrão: TSE oficial)")
    ap.add_argument("--atualizar", action="store_true", help="baixa de novo os arquivos do TSE, ignorando o cache")
    args = ap.parse_args()
    coletar_tse(args.turno, args.base.rstrip("/"), args.atualizar)
    coletar_malhas()
    coletar_2022()
    coletar_abstencao_2022()
