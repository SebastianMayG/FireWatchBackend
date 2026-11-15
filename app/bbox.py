from typing import NamedTuple

from fastapi import HTTPException, Query

from .config import get_settings


class BBox(NamedTuple):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def area_deg2(self) -> float:
        return (self.max_lon - self.min_lon) * (self.max_lat - self.min_lat)


def parse_bbox(raw: str | None) -> BBox:
    """Convierte 'minLon,minLat,maxLon,maxLat' en BBox. Sin valor -> México completo."""
    if raw is None or raw.strip() == "":
        return BBox(*get_settings().default_bbox)
    try:
        parts = [float(p) for p in raw.split(",")]
    except ValueError:
        raise ValueError("bbox debe tener 4 números separados por comas: minLon,minLat,maxLon,maxLat")
    if len(parts) != 4:
        raise ValueError("bbox debe tener 4 números separados por comas: minLon,minLat,maxLon,maxLat")
    b = BBox(*parts)
    if not (-180 <= b.min_lon < b.max_lon <= 180):
        raise ValueError("bbox: se requiere -180 <= minLon < maxLon <= 180")
    if not (-90 <= b.min_lat < b.max_lat <= 90):
        raise ValueError("bbox: se requiere -90 <= minLat < maxLat <= 90")
    # se redondea para que el caché reconozca áreas prácticamente iguales
    return BBox(*(round(v, 4) for v in b))


def bbox_query(
    bbox: str | None = Query(
        None,
        description="Área de interés como `minLon,minLat,maxLon,maxLat` (WGS84). Si se omite, México completo.",
        examples=["-101.5,18.4,-101.2,18.6"],
    ),
) -> BBox:
    """Dependencia de FastAPI: valida el bbox y responde 422 si es inválido."""
    try:
        return parse_bbox(bbox)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
