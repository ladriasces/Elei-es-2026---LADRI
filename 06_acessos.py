"""
06_acessos.py — Relatório de acessos do site no GitHub Pages, a partir do GoatCounter.

O site (docs/index.html) carrega o contador do GoatCounter, que registra as visitas de forma
anônima (sem cookies) e cada aba aberta como "evento". Este script lê a API do GoatCounter e
salva, na pasta relatorios/ (fora do GitHub):
  - relatorio_acessos.html   relatório para abrir no navegador
  - acessos_diarios.csv      visitantes por dia
  - acessos_por_hora.csv     visitantes por hora
  - dados/acessos_AAAA-MM-DD.json   resposta bruta da API (registro do dia em que rodou)

Chave da API: crie em https://ladri.goatcounter.com → Settings → API (permissão
"Read statistics") e salve no arquivo .goatcounter_token, na raiz do projeto, ou na variável
de ambiente GOATCOUNTER_TOKEN.

Uso:
  python 06_acessos.py                      # desde o início da contagem até agora
  python 06_acessos.py --inicio 2026-10-25  # a partir de uma data
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from tse_comum import GOATCOUNTER, RAIZ

API = f"https://{GOATCOUNTER}.goatcounter.com/api/v0"
INICIO_CONTAGEM = "2026-10-21"   # dia em que o contador foi colocado no site
SAIDA = RAIZ / "relatorios"
TOKEN_ARQ = RAIZ / ".goatcounter_token"

TELAS = {"Phones": "Celulares", "Large phones, small tablets": "Celulares grandes e tablets pequenos",
         "Tablets and small laptops": "Tablets e notebooks pequenos", "Computer monitors": "Computadores",
         "Computer monitors larger than HD": "Computadores (telas grandes)", "(unknown)": "Não identificado"}
PAISES = {"Brazil": "Brasil", "United States": "Estados Unidos", "Japan": "Japão", "Germany": "Alemanha",
          "United Kingdom": "Reino Unido", "Spain": "Espanha", "France": "França", "Italy": "Itália",
          "Canada": "Canadá", "Ireland": "Irlanda", "Switzerland": "Suíça", "Netherlands": "Países Baixos",
          "Argentina": "Argentina", "Portugal": "Portugal", "(unknown)": "Não identificado"}
DIRETO = "Acesso direto (link copiado, favoritos, apps)"


def ler_token() -> str:
    tok = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    if not tok and TOKEN_ARQ.exists():
        tok = TOKEN_ARQ.read_text(encoding="utf-8").strip()
    if not tok:
        sys.exit("Chave da API do GoatCounter não encontrada.\n"
                 f"Crie a chave em https://{GOATCOUNTER}.goatcounter.com (Settings → API, permissão 'Read statistics')\n"
                 f"e salve-a no arquivo {TOKEN_ARQ.name}, na raiz do projeto.")
    return tok


def buscar(caminho: str, token: str, **params) -> dict:
    url = f"{API}/{caminho}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                time.sleep(0.3)   # limite da API: 4 requisições por segundo
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 2:
                time.sleep(2)
                continue
            if e.code in (401, 403):
                sys.exit(f"A API do GoatCounter recusou a chave ({e.code}). Confira o arquivo {TOKEN_ARQ.name}.")
            raise


def coletar(token: str, inicio: str, fim: str) -> dict:
    per = {"start": inicio, "end": fim}
    dados = {"periodo": per, "total": buscar("stats/total", token, **per),
             "hits": buscar("stats/hits", token, limit=100, **per)}
    for pagina in ("toprefs", "locations", "systems", "browsers", "sizes"):
        dados[pagina] = buscar(f"stats/{pagina}", token, limit=20, **per)
    return dados


# ---------------------------------------------------------------- relatório
def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def dia_br(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")


def barras_svg(rotulos: list[str], valores: list[int], cada: int = 1, w: int = 880, h: int = 220) -> str:
    """Gráfico de barras simples (SVG), com o valor sobre a barra mais alta."""
    if not valores or max(valores) == 0:
        return '<p class="vazio">Ainda sem visitas registradas neste período.</p>'
    m, ml, mb, mt = max(valores), 36, 28, 18
    n, larg = len(valores), (w - ml) / len(valores)
    y = lambda v: mt + (h - mt - mb) * (1 - v / m)
    partes = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Visitantes">']
    for k in range(5):
        v = round(m * k / 4)
        partes.append(f'<line x1="{ml}" x2="{w}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grade"/>'
                      f'<text x="{ml - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{fmt(v)}</text>')
    pico = valores.index(m)
    for i, (r, v) in enumerate(zip(rotulos, valores)):
        x = ml + i * larg
        partes.append(f'<rect x="{x + larg * .12:.1f}" y="{y(v):.1f}" width="{larg * .76:.1f}" height="{h - mb - y(v):.1f}" rx="2">'
                      f'<title>{r}: {fmt(v)}</title></rect>')
        if i % cada == 0:
            partes.append(f'<text x="{x + larg / 2:.1f}" y="{h - 8}" text-anchor="middle">{r}</text>')
        if i == pico:
            partes.append(f'<text x="{x + larg / 2:.1f}" y="{y(v) - 5:.1f}" text-anchor="middle" class="pico">{fmt(v)}</text>')
    return "".join(partes) + "</svg>"


def tabela(titulo: str, linhas: list[tuple[str, int]], vazio: str = "Sem dados ainda.") -> str:
    """Tabela com barra e participação de cada linha no total da própria tabela."""
    total = sum(c for _, c in linhas)
    if not total:
        return f'<div class="cartao"><h3>{titulo}</h3><p class="vazio">{vazio}</p></div>'
    corpo = "".join(
        f'<tr><td>{html.escape(n)}</td><td class="num">{fmt(c)}</td>'
        f'<td class="barra"><span style="width:{100 * c / max(x[1] for x in linhas):.1f}%"></span></td>'
        f'<td class="num">{100 * c / total:.1f}%</td></tr>'
        for n, c in linhas)
    return f'<div class="cartao"><h3>{titulo}</h3><table>{corpo}</table></div>'


def stats_lista(d: dict, traduz: dict | None = None) -> list[tuple[str, int]]:
    out = []
    for s in d.get("stats") or []:
        nome = s.get("name") or ""
        nome = (traduz or {}).get(nome, nome) or "Não identificado"
        out.append((nome, int(s.get("count") or 0)))
    return out


def gerar(dados: dict) -> None:
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "dados").mkdir(exist_ok=True)
    hoje = date.today().isoformat()
    (SAIDA / "dados" / f"acessos_{hoje}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    dias = [(s["day"], int(s.get("daily") or 0), s.get("hourly") or []) for s in dados["total"].get("stats") or []]
    with open(SAIDA / "acessos_diarios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dia", "visitantes"])
        w.writerows((d, v) for d, v, _ in dias)
    with open(SAIDA / "acessos_por_hora.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dia", "hora", "visitantes"])
        w.writerows((d, h, v) for d, _, hs in dias for h, v in enumerate(hs))

    total = int(dados["total"].get("total") or 0) - int(dados["total"].get("total_events") or 0)
    com_visita = [x for x in dias if x[1] > 0]
    pico = max(dias, key=lambda x: x[1]) if com_visita else None
    media = total / len(dias) if dias else 0
    hora_pico = max(((d, h, v) for d, _, hs in dias for h, v in enumerate(hs)), key=lambda x: x[2], default=None)

    eventos = [h for h in dados["hits"].get("hits") or [] if h.get("event") and str(h.get("path", "")).startswith("aba-")]
    abas = sorted(((h.get("title") or h["path"][4:], int(h.get("count") or 0)) for h in eventos), key=lambda x: -x[1])
    origens = stats_lista(dados["toprefs"], {"": DIRETO, "(no data)": DIRETO})
    locais = stats_lista(dados["locations"], PAISES)
    telas = stats_lista(dados["sizes"], TELAS)
    sistemas = stats_lista(dados["systems"])
    navegadores = stats_lista(dados["browsers"])

    cada = max(1, len(dias) // 12)
    graf_dias = barras_svg([datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d, _, _ in dias], [v for _, v, _ in dias], cada)
    graf_hora = ""
    if pico and pico[2]:
        graf_hora = (f'<div class="cartao"><h3>Visitantes por hora no dia de maior acesso ({dia_br(pico[0])})</h3>'
                     f'{barras_svg([f"{h}h" for h in range(24)], [int(v) for v in pico[2]], 2)}</div>')

    logo = base64.b64encode((RAIZ / "painel" / "logo_ladri.png").read_bytes()).decode("ascii")
    ini, fim = dados["periodo"]["start"][:10], dados["periodo"]["end"][:10]
    kpi = lambda rot, val, det="": f'<div class="kpi"><div class="rot">{rot}</div><div class="val">{val}</div><div class="det">{det}</div></div>'
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acessos · Eleições 2026</title>
<style>
:root {{ --bg:#f4f6f4; --card:#fff; --ink:#121714; --muted:#5d6661; --line:#dfe4e0; --accent:#1d7a3d; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1110; --card:#161a18; --ink:#eef1ef; --muted:#9aa29d; --line:#2a302d; --accent:#3fae63; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 "Segoe UI", system-ui, sans-serif; }}
main {{ max-width: 960px; margin: 0 auto; padding: 28px 16px 48px; }}
header {{ display:flex; align-items:center; gap:18px; margin-bottom: 22px; }}
.logo {{ width:96px; height:60px; flex:none; background:var(--ink); -webkit-mask:url(data:image/png;base64,{logo}) center/contain no-repeat; mask:url(data:image/png;base64,{logo}) center/contain no-repeat; }}
h1 {{ margin:0; font-size:1.7rem; line-height:1.1; }} h3 {{ margin:0 0 10px; font-size:1rem; }}
.sub {{ color:var(--muted); font-size:.88rem; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:12px; margin-bottom:12px; }}
.kpi, .cartao {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.kpi .rot {{ font-size:.78rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
.kpi .val {{ font-size:1.9rem; font-weight:800; line-height:1.15; }} .kpi .det {{ font-size:.82rem; color:var(--muted); }}
.cartao {{ margin-bottom:12px; overflow-x:auto; }}
.duas {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:0 12px; }}
svg {{ width:100%; height:auto; display:block; }} svg rect {{ fill:var(--accent); }}
svg text {{ font-size:11px; fill:var(--muted); }} svg .pico {{ fill:var(--ink); font-weight:700; }} svg .grade {{ stroke:var(--line); }}
table {{ width:100%; border-collapse:collapse; font-size:.9rem; }} td {{ padding:5px 4px; border-top:1px solid var(--line); }}
tr:first-child td {{ border-top:0; }} .num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.barra {{ width:30%; }} .barra span {{ display:block; height:8px; border-radius:4px; background:var(--accent); opacity:.75; }}
.vazio {{ color:var(--muted); margin:0; }}
.nota {{ color:var(--muted); font-size:.82rem; margin-top:18px; }}
</style></head><body><main>
<header><span class="logo" role="img" aria-label="Logo do LADRI"></span><div>
<h1>Relatório de acessos · Eleições 2026</h1>
<div class="sub">Site do LADRI no GitHub Pages · período de {dia_br(ini)} a {dia_br(fim)} · gerado em {datetime.now().strftime("%d/%m/%Y às %H:%M")}</div>
</div></header>
<div class="kpis">
{kpi("Visitantes no período", fmt(total), f"{len(com_visita)} dia(s) com visitas")}
{kpi("Média por dia", fmt(round(media)), f"em {len(dias)} dia(s)")}
{kpi("Dia de maior acesso", dia_br(pico[0]) if pico else "—", f"{fmt(pico[1])} visitantes" if pico else "")}
{kpi("Horário de pico", f"{dia_br(hora_pico[0])[:5]}, {hora_pico[1]}h" if hora_pico and hora_pico[2] else "—", f"{fmt(hora_pico[2])} visitantes nessa hora" if hora_pico and hora_pico[2] else "")}
</div>
<div class="cartao"><h3>Visitantes por dia</h3>{graf_dias}</div>
{graf_hora}
<div class="duas">
{tabela("Abas mais abertas", abas, "Nenhuma aba aberta ainda (a contagem é feita quando o visitante clica numa aba).")}
{tabela("De onde vieram os visitantes", origens)}
{tabela("Localização", locais)}
{tabela("Tipo de tela", telas)}
{tabela("Sistema operacional", sistemas)}
{tabela("Navegador", navegadores)}
</div>
<p class="nota">Fonte: GoatCounter (contagem anônima, sem cookies). Cada visitante é contado uma vez por sessão; quem volta em outro dia conta de novo.
As abas contam quantos visitantes clicaram em cada uma; os percentuais de cada tabela são a participação de cada linha no total dela. Acessos pelo painel no claude.ai não entram nesta contagem.</p>
</main></body></html>
"""
    (SAIDA / "relatorio_acessos.html").write_text(pagina, encoding="utf-8")
    print(f"Visitantes no período: {fmt(total)}" + (f" · dia de maior acesso: {dia_br(pico[0])} ({fmt(pico[1])})" if pico else ""))
    print(f"Relatório salvo em {SAIDA / 'relatorio_acessos.html'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Relatório de acessos do site (GoatCounter).")
    ap.add_argument("--inicio", default=INICIO_CONTAGEM, help="data inicial AAAA-MM-DD (padrão: início da contagem)")
    args = ap.parse_args()
    agora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    gerar(coletar(ler_token(), f"{args.inicio}T00:00:00Z", agora.strftime("%Y-%m-%dT%H:%M:%SZ")))
