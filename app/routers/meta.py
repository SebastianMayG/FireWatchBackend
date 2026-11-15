from fastapi import APIRouter, Request

from ..config import ATTRIBUTION
from ..schemas import Meta

router = APIRouter(tags=["meta"])


@router.get("/health", summary="Estado del servicio")
def health():
    return {"status": "ok"}


@router.get("/meta", response_model=Meta, summary="Años disponibles, sensores, criterios y atribución")
def meta(request: Request):
    db = request.app.state.db
    s = request.app.state.settings
    act = request.app.state.activity
    return {
        "years": db.years,
        "default_year": int(db.meta.get("default_year", db.years[-1])),
        "complete_years": act.complete_years,
        "estimated_years": [y for y in db.years if act.is_estimated(y)],
        "partial_years": [y for y in db.years if act.is_partial(y)],
        "sensors": db.meta.get("sensors", []),
        "default_bbox": list(s.default_bbox),
        "grid_deg": db.grid_deg,
        "points_limit": s.points_limit,
        "recurrent_zones": request.app.state.recurrent.criteria,
        "calibration": db.calibration,
        "quality_report": db.quality,
        "attribution": ATTRIBUTION,
    }
