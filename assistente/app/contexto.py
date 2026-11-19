"""Monta o contexto de cada pergunta: manual inteiro + resumo das tabelas gold (spec §4.3).

Cada bloco leva um rótulo `[fonte: ...]`; os rótulos e os ponto_id expostos
ficam num conjunto, usado na pós-validação contra alucinação.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
SEM_DADOS = "dados indisponíveis no momento (o banco não respondeu ou o pipeline ainda não rodou)."

# Nomes de distrito que também são palavras comuns em pt-BR: exigem pista extra.
AMBIGUOS = {"SE", "SAUDE", "LIBERDADE", "LIMAO"}
_PISTA = r"(?:distrito|bairro|regi[aã]o|subprefeitura)\s+(?:d[aeo]s?\s+)?"


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def normalizar(t: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(t).upper()).strip()


def carregar_manual(caminho: Path) -> dict[str, str]:
    """Divide o manual nas seções `## Título {#id}` → {'manual#id': texto}."""
    texto = Path(caminho).read_text(encoding="utf-8")
    secoes = {}
    for m in re.finditer(r"^## (.+?) \{#([\w-]+)\}\n(.*?)(?=^## |\Z)", texto, re.S | re.M):
        secoes[f"manual#{m.group(2)}"] = f"{m.group(1)}\n{m.group(3).strip()}"
    if not secoes:
        raise ValueError(f"manual sem seções no formato '## Título {{#id}}': {caminho}")
    return secoes


class Repositorio(Protocol):
    def distritos(self) -> list[str]: ...
    def top_ranking(self, n: int) -> list[dict]: ...
    def escuros_agora(self) -> list[dict]: ...
    def top_distritos(self, n: int) -> list[dict]: ...
    def resumo_distrito(self, distrito: str) -> dict | None: ...
    def pontos_distrito(self, distrito: str, n: int) -> list[dict]: ...
    def ultima_execucao(self) -> dict | None: ...


def detectar_distrito(pergunta: str, distritos: list[str]) -> str | None:
    """Distrito citado na pergunta (o nome mais longo vence); None se nenhum."""
    alvo = normalizar(pergunta)
    for d in sorted(distritos, key=len, reverse=True):
        dn = normalizar(d)
        if not re.search(rf"(?<![A-Z0-9]){re.escape(dn)}(?![A-Z0-9])", alvo):
            continue
        if dn in AMBIGUOS:
            com_pista = re.search(_PISTA + re.escape(dn) + r"\b", sem_acento(pergunta), re.I)
            if dn == "SE":
                # "se" conjunção nunca tem acento; "Sé" o distrito tem.
                if not (re.search(r"(?<!\w)sé(?!\w)", pergunta, re.I) or com_pista):
                    continue
            else:
                # exige nome com inicial maiúscula fora do começo da frase, ou pista ("distrito da ...")
                original = re.search(rf"(?<=[^\.\?\!]\s){d[0]}{re.escape(sem_acento(d)[1:].lower())}\b",
                                     sem_acento(pergunta))
                if not (original or com_pista):
                    continue
        return d
    return None


def _hora(ts) -> str:
    if ts is None:
        return "-"
    if isinstance(ts, datetime):
        ts = ts.astimezone(FUSO) if ts.tzinfo else ts.replace(tzinfo=FUSO)
        return ts.strftime("%d/%m/%Y %H:%M")
    return str(ts)


def _linha_ponto(p: dict) -> str:
    return (f"- ponto_id {p['ponto_id']} | {p['nome']} | distrito {p['distrito']} | posição {p['ranking']} | "
            f"índice {float(p['indice_vulnerabilidade']):.3f} | faixa {p['faixa']} | "
            f"ocorrências noturnas a 150 m: {p['ocorrencias_noturnas_150m']} | "
            f"poste mais próximo: {float(p['dist_poste_m']):.0f} m")


@dataclass
class Contexto:
    texto: str
    fontes: set[str] = field(default_factory=set)
    pontos: set[str] = field(default_factory=set)
    tem_dados: bool = False
    distrito: str | None = None


def montar_contexto(pergunta: str, manual: dict[str, str], repo: Repositorio | None) -> Contexto:
    blocos: list[tuple[str, str]] = list(manual.items())
    pontos: set[str] = set()
    tem_dados, distrito = False, None
    try:
        if repo is None:
            raise RuntimeError("sem repositório")
        exec_ = repo.ultima_execucao()
        top = repo.top_ranking(10)
        if not top:
            raise RuntimeError("gold vazio")
        tem_dados = True
        blocos.append(("gold.execucao", "Última atualização dos dados: "
                       + (f"{_hora(exec_['fim'])} (status {exec_['status']})" if exec_ else "desconhecida")))
        blocos.append(("gold.ft_indicador_ponto",
                       "Top 10 do ranking de vulnerabilidade (cidade toda):\n" + "\n".join(map(_linha_ponto, top))))
        pontos |= {p["ponto_id"] for p in top}
        esc = repo.escuros_agora()
        txt = ("Pontos com abrigo escuros agora (lux < 10 na última leitura; leituras SIMULADAS):\n"
               + "\n".join(f"- ponto_id {e['ponto_id']} | {e['nome']} | distrito {e['distrito']} | "
                           f"escuro desde {_hora(e['escuro_desde'])} | lux atual {float(e['lux_atual']):.1f}"
                           for e in esc)) if esc else "Nenhum ponto com abrigo está escuro agora."
        blocos.append(("gold.vw_pontos_escuros_agora", txt))
        pontos |= {e["ponto_id"] for e in esc}
        blocos.append(("gold.ft_resumo_distrito", "Os 5 distritos com maior índice médio:\n" + "\n".join(
            f"- {d['distrito']} (subprefeitura {d['subprefeitura']}): {d['pontos']} pontos, índice médio "
            f"{float(d['indice_medio']):.3f}, {d['pontos_faixa_alta']} na faixa alta, "
            f"{d['ocorrencias_noturnas']} ocorrências noturnas" for d in repo.top_distritos(5))))
        distrito = detectar_distrito(pergunta, repo.distritos())
        if distrito:
            r = repo.resumo_distrito(distrito)
            ps = repo.pontos_distrito(distrito, 5)
            pontos |= {p["ponto_id"] for p in ps}
            blocos.append((f"gold.ft_resumo_distrito#{distrito}", (
                f"Distrito {distrito} (subprefeitura {r['subprefeitura']}): {r['pontos']} pontos, índice médio "
                f"{float(r['indice_medio']):.3f}, {r['pontos_faixa_alta']} na faixa alta, "
                f"{r['ocorrencias_noturnas']} ocorrências noturnas.\n" if r else f"Distrito {distrito}: sem resumo.\n")
                + "Os 5 pontos mais vulneráveis do distrito:\n" + "\n".join(map(_linha_ponto, ps))))
    except Exception:  # noqa: BLE001 — qualquer falha de dados vira "indisponível", nunca derruba a resposta
        blocos = list(manual.items()) + [("gold", SEM_DADOS)]
        pontos, tem_dados, distrito = set(), False, None
    texto = "\n\n".join(f"[fonte: {rot}]\n{conteudo}" for rot, conteudo in blocos)
    return Contexto(texto=texto, fontes={r for r, _ in blocos}, pontos=pontos, tem_dados=tem_dados, distrito=distrito)


class RepositorioPostgres:
    """Leitura do schema gold. Uma conexão por pergunta; fuso de SP na sessão."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._con = None

    def __enter__(self):
        import psycopg2
        import psycopg2.extras
        self._con = psycopg2.connect(self.dsn, connect_timeout=3, options="-c timezone=America/Sao_Paulo",
                                     cursor_factory=psycopg2.extras.RealDictCursor)
        self._con.set_session(readonly=True, autocommit=True)
        return self

    def __exit__(self, *a):
        if self._con:
            self._con.close()

    def _q(self, sql, args=()):
        with self._con.cursor() as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

    _PONTO = """SELECT i.ponto_id, d.nome, d.distrito, i.ranking, i.indice_vulnerabilidade, i.faixa,
                       i.ocorrencias_noturnas_150m, i.dist_poste_m
                FROM gold.ft_indicador_ponto i JOIN gold.dim_ponto d USING (ponto_id)"""

    def distritos(self):
        return [r["distrito"] for r in self._q("SELECT distrito FROM gold.ft_resumo_distrito")]

    def top_ranking(self, n):
        return self._q(self._PONTO + " ORDER BY i.ranking LIMIT %s", (n,))

    def escuros_agora(self):
        return self._q("SELECT * FROM gold.vw_pontos_escuros_agora ORDER BY escuro_desde")

    def top_distritos(self, n):
        return self._q("SELECT * FROM gold.ft_resumo_distrito ORDER BY indice_medio DESC LIMIT %s", (n,))

    def resumo_distrito(self, distrito):
        r = self._q("SELECT * FROM gold.ft_resumo_distrito WHERE distrito = %s", (distrito,))
        return r[0] if r else None

    def pontos_distrito(self, distrito, n):
        return self._q(self._PONTO + " WHERE d.distrito = %s ORDER BY i.ranking LIMIT %s", (distrito, n))

    def ultima_execucao(self):
        r = self._q("SELECT run_id, fim, status FROM gold.execucao ORDER BY fim DESC NULLS LAST LIMIT 1")
        return r[0] if r else None
