from fastapi import APIRouter, Depends, Query, Request

from ..bbox import BBox, bbox_query
from ..config import ATTRIBUTION
from ..deps import activity_service, check_year, year_query
from ..schemas import Calendar, Compare, Indicators, Report, Trend
from ..services.activity import ActivityService

router = APIRouter(tags=["análisis"])

METHODOLOGY = (
    "Actividad armonizada = suma de celdas-día de 1 km con fuego. 2012 en adelante: MODIS + VIIRS S-NPP. "
    "2000-2011: solo MODIS, escalado con un factor de calibración calculado en 2012-2025. "
    "Detalles en docs/metodologia_armonizacion.md."
)


@router.get("/indicators", response_model=Indicators, summary="Indicadores clave del año y área")
def indicators(year: int = Depends(year_query), bbox: BBox = Depends(bbox_query),
               svc: ActivityService = Depends(activity_service)):
    return svc.indicators(year, bbox)


@router.get("/calendar", response_model=Calendar, summary="Matriz años × meses de actividad")
def calendar(bbox: BBox = Depends(bbox_query), svc: ActivityService = Depends(activity_service)):
    return svc.calendar(bbox)


@router.get("/trend", response_model=Trend, summary="Serie anual de actividad")
def trend(bbox: BBox = Depends(bbox_query), svc: ActivityService = Depends(activity_service)):
    return svc.trend(bbox)


@router.get("/compare", response_model=Compare, summary="Compara dos años en la misma área")
def compare(request: Request,
            year_a: int = Query(..., description="Periodo principal"),
            year_b: int = Query(..., description="Periodo a comparar"),
            bbox: BBox = Depends(bbox_query), svc: ActivityService = Depends(activity_service)):
    return svc.compare(check_year(request, year_a, "year_a"), check_year(request, year_b, "year_b"), bbox)


@router.get("/report", response_model=Report, summary="Todo lo necesario para el reporte PDF en una llamada")
def report(year: int = Depends(year_query), bbox: BBox = Depends(bbox_query),
           svc: ActivityService = Depends(activity_service)):
    return {
        "bbox": list(bbox),
        "year": year,
        "indicators": svc.indicators(year, bbox),
        "trend": svc.trend(bbox),
        "calendar": svc.calendar(bbox),
        "methodology": METHODOLOGY,
        "attribution": ATTRIBUTION,
    }
