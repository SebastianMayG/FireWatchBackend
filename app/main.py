"""FireWatch API.

Correr en local:  uvicorn app.main:app --reload
Documentación interactiva: http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import ATTRIBUTION, Settings, get_settings
from .db import Database
from .routers import analysis, maps, meta
from .services.activity import ActivityService
from .services.hotspots import HotspotService
from .services.recurrent import RecurrentZoneService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.data_dir)
        app.state.settings = settings
        app.state.db = db
        app.state.activity = ActivityService(db, settings)
        app.state.hotspots = HotspotService(db, settings)
        app.state.recurrent = RecurrentZoneService(db, settings)  # se precalcula al arrancar
        yield
        db.close()

    app = FastAPI(
        title="FireWatch API",
        version="0.1.0",
        description=(
            "Análisis histórico de puntos calientes en México con datos armonizados de MODIS y VIIRS "
            "(NASA FIRMS). Metodología en `docs/metodologia_armonizacion.md`.\n\n"
            f"**Atribución:** {ATTRIBUTION}"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Attribution"],
    )
    for r in (meta.router, maps.router, analysis.router):
        app.include_router(r)
    return app


app = create_app()
