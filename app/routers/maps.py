from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..bbox import BBox, bbox_query
from ..config import ATTRIBUTION
from ..deps import hotspot_service, recurrent_service, year_query
from ..services.hotspots import HotspotService, MinConf
from ..services.recurrent import RecurrentZoneService

router = APIRouter(tags=["mapa"])

MIN_CONF = Query("low", description="Confianza mínima: `low` (todas), `nominal` o `high`")


@router.get(
    "/hotspots",
    summary="Puntos calientes del año y área (puntos reales o rejilla agregada)",
    description=(
        "Si el área tiene pocas detecciones (≤ `points_limit`, ver /meta) responde `mode: \"points\"` "
        "con un GeoJSON FeatureCollection. Si tiene más, responde `mode: \"grid\"` con celdas agregadas "
        "`[lat, lon, count, frp_max]` para pintarlas como heatmap."
    ),
)
def hotspots(year: int = Depends(year_query), bbox: BBox = Depends(bbox_query), min_conf: MinConf = MIN_CONF,
             svc: HotspotService = Depends(hotspot_service)):
    return svc.get(year, bbox, min_conf)


@router.get("/recurrent-zones", summary="Polígonos de zonas de incendios recurrentes (GeoJSON)")
def recurrent_zones(bbox: BBox = Depends(bbox_query), svc: RecurrentZoneService = Depends(recurrent_service)):
    return svc.get(bbox)


@router.get("/export/csv", summary="Descarga CSV de las detecciones del año y área", tags=["exportación"])
def export_csv(year: int = Depends(year_query), bbox: BBox = Depends(bbox_query), min_conf: MinConf = MIN_CONF,
               svc: HotspotService = Depends(hotspot_service)):
    name = f"firewatch_{year}_{'_'.join(f'{v:g}' for v in bbox)}.csv"
    return StreamingResponse(
        svc.iter_csv(year, bbox, min_conf),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Attribution": ATTRIBUTION,
            "Access-Control-Expose-Headers": "Content-Disposition, X-Attribution",
        },
    )
