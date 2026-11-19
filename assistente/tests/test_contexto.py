import pytest

from app.contexto import SEM_DADOS, carregar_manual, detectar_distrito, montar_contexto
from conftest import RepoFalso

DISTRITOS = RepoFalso().distritos()


@pytest.mark.parametrize("pergunta,esperado", [
    ("Quais os pontos mais vulneráveis de Pinheiros?", "PINHEIROS"),
    ("pontos da Sé", "SE"),
    ("e no distrito da se?", "SE"),
    ("O que acontece se o ponto apagar?", None),
    ("Se eu quiser exportar o ranking?", None),
    ("Como está a Cidade Dutra?", "CIDADE DUTRA"),
    ("ranking no Jardim Paulista", "JARDIM PAULISTA"),  # nome mais longo vence
    ("a saúde dos dados está ok?", None),
    ("Pontos na Saúde e no Jabaquara", "SAUDE"),
    ("Liberdade de expressão no painel?", None),
    ("e o bairro da liberdade?", "LIBERDADE"),
    ("consolação", "CONSOLACAO"),
])
def test_detectar_distrito(pergunta, esperado):
    assert detectar_distrito(pergunta, DISTRITOS) == esperado


def test_manual_em_secoes(cfg):
    m = carregar_manual(cfg.manual_path)
    assert {"manual#alertas", "manual#indice", "manual#privacidade", "manual#telas"} <= set(m)


def test_contexto_com_dados(cfg, repo):
    ctx = montar_contexto("pontos de Pinheiros", carregar_manual(cfg.manual_path), repo)
    assert ctx.tem_dados and ctx.distrito == "PINHEIROS"
    assert {"111", "222", "333", "444"} == ctx.pontos
    assert "gold.ft_resumo_distrito#PINHEIROS" in ctx.fontes and "manual#alertas" in ctx.fontes
    assert "escuro desde 17/11/2026 18:00" in ctx.texto  # 21:00 UTC exibido no fuso de SP
    assert "[fonte: gold.execucao]" in ctx.texto


@pytest.mark.parametrize("repo_", [None, RepoFalso(vazio=True), RepoFalso(quebrado=True)])
def test_contexto_sem_dados(cfg, repo_):
    ctx = montar_contexto("pontos de Pinheiros", carregar_manual(cfg.manual_path), repo_)
    assert not ctx.tem_dados and ctx.pontos == set()
    assert SEM_DADOS in ctx.texto and "manual#indice" in ctx.fontes


def test_contexto_nunca_lista_todos_os_pontos(cfg, repo):
    ctx = montar_contexto("qualquer coisa", carregar_manual(cfg.manual_path), repo)
    assert len(ctx.pontos) <= 10 + 50 + 5
