import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import scheduler
from .api import auth_router, router
from .auth import bootstrap_users
from .config import get_settings
from .db import engine, init_db
from .mcp_server import Router, mcp
from .profile import migrate_profiles, seed_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ai-job-finder")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    init_db()
    with Session(engine) as session:
        bootstrap_users(session)
        migrate_profiles(session)
        seed_profile(session)
    if s.secret_key == "troque-isto":
        log.warning("SECRET_KEY padrão: defina uma no .env antes de expor o app")
    scheduler.start()
    async with mcp.session_manager.run():
        yield
    scheduler.stop()


web = FastAPI(title="AI-JOB-FINDER", lifespan=lifespan)
web.include_router(auth_router)
web.include_router(router)


@web.get("/api/health")
def health():
    return {"ok": True}


dist = get_settings().frontend_dist
if dist.is_dir():
    web.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @web.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "não encontrado"}, status_code=404)
        f = dist / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(dist / "index.html")


app = Router(web)
