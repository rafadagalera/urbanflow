"""API do assistente UrbanCare: POST /perguntar, GET /saude, GET / (chat)."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Config
from .contexto import RepositorioPostgres, carregar_manual, montar_contexto
from .llm import Assistente, ClienteHTTP
from .schema import Pergunta, Resposta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("assistente")
STATIC = Path(__file__).parent / "static"


def repo_postgres(cfg: Config):
    @contextmanager
    def abrir():
        if not cfg.database_url:
            yield None
            return
        try:
            r = RepositorioPostgres(cfg.database_url).__enter__()
        except Exception as e:  # noqa: BLE001 — banco fora do ar: segue sem dados
            log.warning("gold indisponível: %s", type(e).__name__)
            yield None
            return
        try:
            yield r
        finally:
            r.__exit__(None, None, None)
    return abrir


def criar_app(cfg: Config | None = None, cliente=None, abrir_repo=None) -> FastAPI:
    cfg = cfg or Config()
    manual = carregar_manual(cfg.manual_path)
    sistema = cfg.prompt_path.read_text(encoding="utf-8")
    assistente = Assistente(cfg, cliente or ClienteHTTP(cfg), sistema)
    abrir_repo = abrir_repo or repo_postgres(cfg)
    app = FastAPI(title="Assistente UrbanCare", version="1.0")

    @app.post("/perguntar", response_model=Resposta)
    def perguntar(p: Pergunta) -> Resposta:
        with abrir_repo() as repo:
            ctx = montar_contexto(p.pergunta, manual, repo)
        return assistente.perguntar(p.pergunta, ctx).resposta

    @app.get("/saude")
    def saude():
        ultima, dados = None, False
        with abrir_repo() as repo:
            if repo is not None:
                try:
                    e = repo.ultima_execucao()
                    dados = bool(repo.top_ranking(1))
                    ultima = e and {"fim": e["fim"].isoformat() if e["fim"] else None, "status": e["status"]}
                except Exception:  # noqa: BLE001
                    dados = False
        return {"modelo": cfg.modelo, "modelo_reserva": cfg.modelo_reserva, "chave_presente": bool(cfg.api_key),
                "dados_gold": dados, "ultima_execucao": ultima}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    return app


app = criar_app()
