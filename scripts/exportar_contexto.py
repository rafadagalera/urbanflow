"""Exporta o contexto do assistente para web/contexto.json (chat publicado na Azure).

O chat Node da Azure não alcança o Postgres. Este script roda localmente, usa o
mesmo `montar_contexto` do FastAPI e grava os blocos de texto já renderizados:
o Node só concatena, e as mensagens enviadas ao modelo ficam idênticas às do Python.

Uso (na raiz do repositório, com o Postgres do docker compose no ar):
  set -a; . ./.env; set +a
  DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:55432/urbancare" \
    python scripts/exportar_contexto.py [saida.json]

Conteúdo: seções do manual, blocos globais (execução, top 10, escuros agora, top 5
distritos), lista de distritos (na ordem do banco: o desempate da detecção depende
dela), bloco de cada distrito com seus ponto_id, e o estado para /api/saude.
Nenhum segredo nem dado pessoal: só nomes de pontos de ônibus, distritos e números.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "assistente"))

from app.contexto import FUSO, RepositorioPostgres, carregar_manual, montar_contexto  # noqa: E402

SAIDA_PADRAO = RAIZ / "web/contexto.json"
VERSAO = 1


class RepoFotografia:
    """Memoriza cada consulta: o arquivo inteiro sai de um único retrato do banco,
    mesmo que o Airflow grave leituras novas durante a exportação."""

    def __init__(self, repo, distritos: list[str] | None = None):
        self._repo, self._cache = repo, {}
        self._distritos = distritos

    def _memo(self, nome, *args):
        chave = (nome, args)
        if chave not in self._cache:
            self._cache[chave] = getattr(self._repo, nome)(*args)
        return self._cache[chave]

    def com_distritos(self, distritos: list[str]) -> "RepoFotografia":
        outro = RepoFotografia(self._repo, distritos)
        outro._cache = self._cache  # mesmo retrato
        return outro

    def distritos(self):
        return list(self._distritos) if self._distritos is not None else self._memo("distritos")

    def top_ranking(self, n):
        return self._memo("top_ranking", n)

    def escuros_agora(self):
        return self._memo("escuros_agora")

    def top_distritos(self, n):
        return self._memo("top_distritos", n)

    def resumo_distrito(self, d):
        return self._memo("resumo_distrito", d)

    def pontos_distrito(self, d, n):
        return self._memo("pontos_distrito", d, n)

    def ultima_execucao(self):
        return self._memo("ultima_execucao")


def _cabecalho(rot: str) -> str:
    return f"[fonte: {rot}]\n"


def _separar_blocos(texto: str, rotulos: list[str]) -> list[list[str]]:
    """Corta o texto montado em [(rótulo, conteúdo)], na ordem em que aparecem."""
    posicoes = sorted((texto.index(_cabecalho(r)), r) for r in rotulos)
    blocos = []
    for i, (pos, rot) in enumerate(posicoes):
        fim = posicoes[i + 1][0] - 2 if i + 1 < len(posicoes) else len(texto)
        blocos.append([rot, texto[pos + len(_cabecalho(rot)):fim]])
    return blocos


def _juntar(blocos) -> str:
    return "\n\n".join(_cabecalho(r) + c for r, c in blocos)


def exportar(repo, manual: dict[str, str], agora: datetime | None = None) -> dict:
    """Monta o dicionário do contexto.json usando o próprio montar_contexto."""
    foto = RepoFotografia(repo) if repo is not None else None
    manual_blocos = [[r, c] for r, c in manual.items()]

    base = montar_contexto("", manual, foto.com_distritos([]) if foto else None)
    rotulos_gold = [r for r in base.fontes if r not in manual]
    prefixo = _juntar(manual_blocos)
    assert base.texto.startswith(prefixo + "\n\n"), "o manual deveria abrir o contexto"
    globais = _separar_blocos(base.texto[len(prefixo) + 2:], rotulos_gold)
    assert _juntar(manual_blocos + globais) == base.texto, "blocos globais não reconstroem o contexto"

    distritos, por_distrito = [], {}
    if base.tem_dados:
        distritos = foto.distritos()
        for d in distritos:
            ctx = montar_contexto(f"distrito {d}", manual, foto.com_distritos([d]))
            assert ctx.tem_dados and ctx.distrito == d, f"distrito não detectado na exportação: {d}"
            assert ctx.texto.startswith(base.texto + "\n\n")
            (rot,) = ctx.fontes - base.fontes
            sufixo = ctx.texto[len(base.texto) + 2:]
            assert sufixo.startswith(_cabecalho(rot))
            pontos = sorted({p["ponto_id"] for p in foto.pontos_distrito(d, 5)})
            assert base.pontos | set(pontos) == ctx.pontos
            por_distrito[d] = {"fonte": rot, "bloco": sufixo[len(_cabecalho(rot)):], "pontos": pontos}

    # /api/saude: mesmo formato do FastAPI (main.py)
    ultima = None
    if base.tem_dados:
        e = foto.ultima_execucao()
        ultima = e and {"fim": e["fim"].isoformat() if e["fim"] else None, "status": e["status"]}

    return {
        "versao": VERSAO,
        "gerado_em": (agora or datetime.now(FUSO)).isoformat(timespec="seconds"),
        "tem_dados": base.tem_dados,
        "manual": dict(manual),
        "blocos_globais": globais,
        "pontos_globais": sorted(base.pontos),
        "distritos": distritos,
        "por_distrito": por_distrito,
        "saude": {"dados_gold": base.tem_dados, "ultima_execucao": ultima},
    }


def main(argv: list[str]) -> int:
    saida = Path(argv[1]) if len(argv) > 1 else SAIDA_PADRAO
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("defina DATABASE_URL (veja o cabeçalho deste script)", file=sys.stderr)
        return 2
    manual = carregar_manual(Path(os.environ.get("MANUAL_PATH") or RAIZ / "docs/manual.md"))
    with RepositorioPostgres(dsn) as repo:
        dados = exportar(repo, manual)
    if not dados["tem_dados"]:
        print("ATENÇÃO: gold vazio ou indisponível; o contexto exportado não tem dados.", file=sys.stderr)
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{saida}: {len(dados['distritos'])} distritos, {len(dados['pontos_globais'])} pontos globais, "
          f"gerado_em {dados['gerado_em']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
