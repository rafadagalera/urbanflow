"""Gera os PDFs das entregas a partir dos READMEs de cada disciplina.

Uma única fonte: o README do GitHub e o PDF do portal têm o mesmo conteúdo.
- Big Data: pipeline/README.md  → entregas/big-data/UrbanCare-BigData.pdf
- GenAI:    assistente/README.md → entregas/genai/UrbanCare-GenAI.pdf

Requer `mistune` (pip install mistune) e Google Chrome ou Chromium no PATH.
Diagramas Mermaid são desenhados pelo Chrome com o mermaid.js da jsDelivr (precisa de rede).

    python3 scripts/gerar_pdfs.py            # os dois
    python3 scripts/gerar_pdfs.py genai      # só um
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mistune

RAIZ = Path(__file__).resolve().parents[1]
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

ENTREGAS = {
    "bigdata": dict(
        readme=RAIZ / "pipeline" / "README.md",
        saida=RAIZ / "entregas" / "big-data" / "UrbanCare-BigData.pdf",
        titulo="UrbanCare<br>Pipeline de dados",
        disciplina="Big Data Architecture &amp; Data Integration<br>Profa. Ana Machado",
        resumo="Arquitetura, dicionário de dados, justificativa dos parâmetros, evidências e limitações.",
        pasta="pipeline/",
    ),
    "genai": dict(
        readme=RAIZ / "assistente" / "README.md",
        saida=RAIZ / "entregas" / "genai" / "UrbanCare-GenAI.pdf",
        titulo="UrbanCare<br>Assistente do painel",
        disciplina="Generative AI for Engineering<br>Prof. Reinaldo",
        resumo="Problema, arquitetura, escolha do modelo, engenharia de prompts, exemplos reais, "
               "tratamento de falhas, limitações e aspectos éticos.",
        pasta="assistente/",
    ),
}
REPO = "https://github.com/rafadagalera/urbanflow"

EQUIPE = [
    ("Beatriz Silva Pinheiro Rocha", "RM553455"),
    ("Enzzo Monteiro Barros Silva", "RM552616"),
    ("Iago Diniz Fontes", "RM553776"),
    ("Larissa Estella Gonçalves dos Santos", "RM552695"),
    ("Rafael Alves do Nascimento", "RM553117"),
]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 9.6pt; line-height: 1.45; color: #1f2328; }
h1 { font-size: 19pt; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5px solid #d0d7de; break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }
p, ul { margin: 0 0 6pt; }
ul { padding-left: 16pt; }
li { margin: 1.5pt 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.4pt; background: #f2f4f6; padding: 0 2px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 4px; padding: 6pt 8pt; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.4pt; }
th, td { border: 1px solid #d0d7de; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #f2f4f6; }
tr { break-inside: avoid; }
img { display: block; max-width: 100%; max-height: 120mm; margin: 6pt auto 10pt; border: 1px solid #d0d7de; break-inside: avoid; }
img[src$=".svg"] { border: none; max-height: none; }
a { color: #0b57d0; text-decoration: none; }
.capa { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; break-after: page; }
.capa .topo { color: #57606a; font-size: 10pt; }
.capa .titulo { font-size: 28pt; font-weight: bold; margin: 0; line-height: 1.15; }
.capa .sub { font-size: 14pt; color: #424a53; margin: 8pt 0 0; }
.capa table { width: auto; font-size: 10pt; }
.capa td { border: none; padding: 1.5pt 14pt 1.5pt 0; }
.mermaid { background: none; border: none; text-align: center; break-inside: avoid; }
.mermaid svg { max-width: 100% !important; max-height: 200mm; width: auto; height: auto; }
.capa .faixa { height: 6px; background: linear-gradient(90deg, #a5672e, #6e7781, #9a7d0a); margin: 14pt 0; }
"""


def capa(e: dict) -> str:
    linhas = "".join(f"<tr><td>{n}</td><td>{rm}</td></tr>" for n, rm in EQUIPE)
    return f"""
<section class="capa">
  <div class="topo">FIAP · Engenharia de Software · 4º ano<br>Global Solution CitizenTech · 2º semestre de 2026</div>
  <div>
    <p class="titulo">{e["titulo"]}</p>
    <p class="sub">{e["disciplina"]}</p>
    <div class="faixa"></div>
    <p>{e["resumo"]}<br>
    Repositório: <a href="{REPO}">{REPO}</a> (pasta <code>{e["pasta"]}</code>)</p>
  </div>
  <div><strong>Equipe</strong><table>{linhas}</table><p style="margin-top:10pt">Novembro de 2026</p></div>
</section>"""


def ajustar_caminhos(html: str, base: Path) -> str:
    """Imagens viram file:// absoluto; demais links relativos apontam para o GitHub."""

    def img(m):
        return f'{m.group(1)}="{(base / m.group(2)).resolve().as_uri()}"'

    def link(m):
        alvo = (base / m.group(2)).resolve().relative_to(RAIZ).as_posix()
        return f'{m.group(1)}="{REPO}/blob/master/{alvo}"'

    html = re.sub(r'(src)="(?!https?:|file:)([^"]+)"', img, html)
    return re.sub(r'(href)="(?!https?:|#|mailto:)([^"]+)"', link, html)


def chrome() -> str:
    for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if caminho := shutil.which(nome):
            return caminho
    sys.exit("Chrome/Chromium não encontrado no PATH")


def mermaid(html: str) -> tuple[str, str]:
    """Blocos ```mermaid viram <pre class="mermaid">; devolve o HTML e o script (vazio se não houver)."""
    html, n = re.subn(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                      r'<pre class="mermaid">\1</pre>', html, flags=re.S)
    if not n:
        return html, ""
    return html, (f'<script src="{MERMAID_JS}"></script>'
                  '<script>mermaid.initialize({startOnLoad: true, theme: "neutral", securityLevel: "loose"});</script>')


def gerar(nome: str) -> None:
    e = ENTREGAS[nome]
    md = e["readme"].read_text(encoding="utf-8")
    corpo = mistune.create_markdown(plugins=["table"], escape=False)(md)
    corpo, script = mermaid(ajustar_caminhos(corpo, e["readme"].parent))
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>UrbanCare</title><style>{CSS}</style></head>
<body>{capa(e)}{corpo}{script}</body></html>"""
    e["saida"].parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        pagina = Path(tmp) / "relatorio.html"
        pagina.write_text(html, encoding="utf-8")
        subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", "--virtual-time-budget=20000",
                        f"--print-to-pdf={e['saida']}", pagina.as_uri()],
                       check=True, capture_output=True)
    print(f"PDF gerado: {e['saida'].relative_to(RAIZ)} ({e['saida'].stat().st_size // 1024} KB)")


def main():
    nomes = sys.argv[1:] or list(ENTREGAS)
    for nome in nomes:
        if nome not in ENTREGAS:
            sys.exit(f"entrega desconhecida: {nome} (use {', '.join(ENTREGAS)})")
        gerar(nome)


if __name__ == "__main__":
    main()
