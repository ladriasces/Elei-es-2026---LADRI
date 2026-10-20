# Eleições 2026 · Eleição presidencial (1º e 2º turnos)

**LADRI — Laboratório de Dados e Relações Internacionais · ASCES-UNITA**

Análise descritiva e georreferenciada da eleição presidencial de 2026 — 1º turno (4 de outubro) e 2º turno (25 de outubro), com acompanhamento da apuração ao vivo — com dados oficiais do Tribunal Superior Eleitoral (TSE).

🔗 **Painel interativo:** https://ladriasces.github.io/Elei-es-2026---LADRI/

**1º turno**

| | Flávio Bolsonaro (PL) | Lula (PT) |
|---|---|---|
| Votos válidos | 47,03% | 45,16% |
| Votos | 56.104.503 | 53.879.538 |
| Municípios vencidos | 2.908 | 2.663 |

Nenhum candidato alcançou mais de 50% dos votos válidos; os dois disputam o 2º turno em 25 de outubro.

## O que tem aqui

- **Painel interativo** ([`docs/index.html`](docs/index.html)): visão geral, **2º turno ao vivo**, mapa por município, análise por região, análise por estado (com mesorregiões), abstenção (com comparação com 2022), brasileiros no exterior e comparação com 2022. Um seletor "1º turno | 2º turno" no topo faz todas as abas mostrarem o turno escolhido.
- **Notebook didático** ([`analise_eleicoes_2026.ipynb`](analise_eleicoes_2026.ipynb)): como usar a API do TSE, estatística descritiva, mapas com geopandas, exterior e 2022.
- **Tabelas tratadas** ([`data/processed/`](data/processed/)): resultados por candidato, UF, município e país, prontos para análise.

## Como reproduzir

```bash
pip install -r requirements.txt
python 01_coleta.py          # baixa os resultados do TSE (2026 e 2022) e as malhas do IBGE (data/raw/)
python 02_tratamento.py      # monta as tabelas em data/processed/
python 03_painel.py          # gera o painel (painel/index.html e docs/index.html)
```

Para o 2º turno, use `--turno 2` na coleta e no tratamento (as saídas vão para `data/raw/tse_2t/` e `data/processed/2t/`).

## 2º turno ao vivo

Durante a apuração, a aba **2º turno ao vivo** lê a API do TSE diretamente no navegador de quem acessa o site, a cada minuto: placar, % de seções apuradas, andamento por estado, mapa por estado e por município (que vai se completando), curva da apuração e a comparação com o 1º turno. Nada precisa ficar ligado no servidor do LADRI. Os números são oficiais e parciais; a plataforma não faz projeções.

O motor ao vivo (em `painel/template.html`) reproduz em JavaScript as mesmas regras do tratamento em Python (`tse_comum.py`). Num teste com a apuração completa simulada, os 115.300 valores montados no navegador (candidatos, resumo, estados, municípios, países e cidades no exterior) foram idênticos aos gerados pelo pipeline.

Depois da totalização final, os dados do 2º turno são gravados no próprio painel, que deixa de depender da API:

```bash
python 01_coleta.py --turno 2 --atualizar
python 02_tratamento.py --turno 2
python 03_painel.py
git add -A && git commit -m "2º turno: resultado final" && git push
```

O `03_painel.py` só embute o 2º turno quando o TSE marca a totalização como final. A versão do painel publicada no claude.ai não consegue acessar a API do TSE (restrição de segurança da plataforma); o acompanhamento ao vivo funciona no site do GitHub Pages.

Os dados brutos (~690 MB, incluindo o arquivo de 2022 do [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/)) não ficam no repositório por causa do tamanho; o `01_coleta.py` baixa tudo.

Para só explorar os dados, não é preciso rodar a coleta: o notebook usa as tabelas de `data/processed/` e baixa sozinho os poucos arquivos brutos de que precisa.

## Fontes

- **Resultados 2026:** API pública de divulgação de resultados do TSE (`resultados.tse.jus.br`), eleições 6257 (1º turno) e 6258 (2º turno), cargo Presidente. Um arquivo por município (5.571) e por cidade no exterior (186).
- **Resultados 2022:** Portal de Dados Abertos do TSE, `votacao_candidato_munzona_2022` (votos) e `detalhe_votacao_munzona_2022` (comparecimento e abstenção), 1º e 2º turnos, Presidente. Cada turno de 2026 é comparado com o mesmo turno de 2022.
- **Malhas e divisão regional:** API de malhas e de localidades do IBGE.
- **Mapa-múndi:** Natural Earth (1:110 milhões).

## Notas de método

- Percentuais dos candidatos são calculados sobre os **votos válidos** (sem brancos e nulos).
- **Abstenção geral** (21,1%) inclui os eleitores no exterior; **só no Brasil**, a abstenção foi de 20,8%. Em 2022, os mesmos números foram 20,95% e 20,79%.
- O país de cada cidade no exterior foi atribuído manualmente ([`exterior_paises.py`](exterior_paises.py)), pois o TSE informa só a cidade-sede da seção.
- A comparação com 2022 usa o candidato do PL de cada ano (Jair Bolsonaro em 2022, Flávio Bolsonaro em 2026).
- Conferência: a soma de municípios e exterior é igual ao total nacional divulgado pelo TSE (119.300.788 votos válidos).

## Como esta plataforma foi feita

Esta plataforma foi desenvolvida pelo LADRI com o auxílio do **Claude**, assistente de inteligência artificial da Anthropic. O Claude ajudou a escrever o código de coleta, tratamento e análise dos dados, o painel interativo, o notebook e as visualizações. A definição dos recortes e a revisão do conteúdo foram feitas pela equipe do LADRI, e os totais foram conferidos com os números oficiais divulgados pelo TSE.

## Estrutura

```
tse_comum.py               funções e constantes comuns (leitura do TSE, 2022, pastas por turno)
01_coleta.py               coleta (TSE + IBGE)
02_tratamento.py           tratamento e junções
03_painel.py               gera o painel a partir de painel/template.html
exterior_paises.py         cidade no exterior -> país/continente
analise_eleicoes_2026.ipynb  notebook didático
data/processed/            tabelas tratadas
docs/                      site do GitHub Pages
figuras/                   gráficos gerados pelo notebook
painel/                    modelo e versão do painel
```
