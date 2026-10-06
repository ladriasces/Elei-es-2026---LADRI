# Eleições 2026 · 1º turno presidencial

**LADRI — Laboratório de Dados e Relações Internacionais · ASCES-UNITA**

Análise descritiva e georreferenciada do 1º turno da eleição presidencial de 4 de outubro de 2026, com dados oficiais do Tribunal Superior Eleitoral (TSE).

🔗 **Painel interativo:** https://ladriasces.github.io/Elei-es-2026---LADRI/

| | Flávio Bolsonaro (PL) | Lula (PT) |
|---|---|---|
| Votos válidos | 47,03% | 45,16% |
| Votos | 56.104.503 | 53.879.538 |
| Municípios vencidos | 2.908 | 2.663 |

Nenhum candidato alcançou mais de 50% dos votos válidos; os dois disputam o 2º turno em 25 de outubro.

## O que tem aqui

- **Painel interativo** ([`docs/index.html`](docs/index.html)): visão geral, mapa por município, análise por estado (com mesorregiões), brasileiros no exterior e comparação com 2022.
- **Notebook didático** ([`analise_eleicoes_2026.ipynb`](analise_eleicoes_2026.ipynb)): como usar a API do TSE, estatística descritiva, mapas com geopandas, exterior e 2022.
- **Artes para redes sociais** ([`instagram/`](instagram/)): mapas e gráficos em 1:1, 9:16 (stories) e 16:9.
- **Tabelas tratadas** ([`data/processed/`](data/processed/)): resultados por candidato, UF, município e país, prontos para análise.

## Como reproduzir

```bash
pip install -r requirements.txt
python 01_coleta.py          # baixa os resultados do TSE e as malhas do IBGE (data/raw/)
python 02_tratamento.py      # monta as tabelas em data/processed/
python 03_painel.py          # gera o painel (painel/index.html e docs/index.html)
python 04_instagram.py       # gera as artes 1:1 em instagram/
python 05_stories_exterior.py  # gera as artes do exterior em 9:16 e 16:9
```

O arquivo de 2022 (`votacao_candidato_munzona_2022.zip`, ~640 MB) precisa ser baixado do [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/) e colocado em `data/raw/`. Os dados brutos não ficam no repositório por causa do tamanho.

As artes usam a família de fontes Segoe UI, presente no Windows.

## Fontes

- **Resultados 2026:** API pública de divulgação de resultados do TSE (`resultados.tse.jus.br`), eleição 6257, cargo Presidente. Um arquivo por município (5.571) e por cidade no exterior (186).
- **Resultados 2022:** Portal de Dados Abertos do TSE, `votacao_candidato_munzona_2022`, 1º turno, Presidente.
- **Malhas e divisão regional:** API de malhas e de localidades do IBGE.
- **Mapa-múndi:** Natural Earth (1:110 milhões).

## Notas de método

- Percentuais dos candidatos são calculados sobre os **votos válidos** (sem brancos e nulos).
- **Abstenção geral** (21,1%) inclui os eleitores no exterior; **só no Brasil**, a abstenção foi de 20,8%.
- O país de cada cidade no exterior foi atribuído manualmente ([`exterior_paises.py`](exterior_paises.py)), pois o TSE informa só a cidade-sede da seção.
- A comparação com 2022 usa o candidato do PL de cada ano (Jair Bolsonaro em 2022, Flávio Bolsonaro em 2026).
- Conferência: a soma de municípios e exterior é igual ao total nacional divulgado pelo TSE (119.300.788 votos válidos).

## Estrutura

```
01_coleta.py               coleta (TSE + IBGE)
02_tratamento.py           tratamento e junções
03_painel.py               gera o painel a partir de painel/template.html
04_instagram.py            artes 1:1
05_stories_exterior.py     artes do exterior (9:16 e 16:9)
exterior_paises.py         cidade no exterior -> país/continente
analise_eleicoes_2026.ipynb  notebook didático
data/processed/            tabelas tratadas
docs/                      site do GitHub Pages
figuras/                   gráficos gerados pelo notebook
instagram/                 artes para redes sociais
painel/                    modelo e versão do painel
```
