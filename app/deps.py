"""Dependencias compartidas por los routers (servicios y validación de año)."""
from fastapi import HTTPException, Query, Request

from .services.activity import ActivityService
from .services.hotspots import HotspotService
from .services.recurrent import RecurrentZoneService


def activity_service(request: Request) -> ActivityService:
    return request.app.state.activity


def hotspot_service(request: Request) -> HotspotService:
    return request.app.state.hotspots


def recurrent_service(request: Request) -> RecurrentZoneService:
    return request.app.state.recurrent


def check_year(request: Request, year: int | None, name: str = "year") -> int:
    db = request.app.state.db
    if year is None:
        return int(db.meta.get("default_year", db.years[-1]))
    if year not in db.years:
        raise HTTPException(422, f"{name}={year} fuera de rango; años disponibles: {db.years[0]}-{db.years[-1]}")
    return year


def year_query(
    request: Request,
    year: int | None = Query(None, description="Año a analizar. Si se omite, el más reciente disponible."),
) -> int:
    return check_year(request, year)
