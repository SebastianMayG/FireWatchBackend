"""Zonas de incendios recurrentes (diferenciador de FireWatch).

Criterio (configurable en Settings, documentado en docs/metodologia_armonizacion.md):
- La rejilla de 1 km (0.01°) se agrupa en zonas de zone_factor × zone_factor celdas (0.05°, ~5 km).
- Un año cuenta como "activo" para la zona si tuvo >= recurrent_min_cell_days celdas-día
  detectadas por MODIS. Se usa solo MODIS para medir igual los 25 años (2001-2025).
- Una zona es recurrente si tiene >= recurrent_min_years años activos.
- Las zonas recurrentes vecinas se unen en polígonos.
Se calcula una vez al arrancar y queda en memoria.
"""
import shapely
from shapely.geometry import Point, box, mapping
from shapely.strtree import STRtree

from ..bbox import BBox
from ..config import Settings
from ..db import Database


class RecurrentZoneService:
    def __init__(self, db: Database, settings: Settings):
        self.settings = settings
        self.zone_deg = round(db.grid_deg * settings.zone_factor, 6)
        f = settings.zone_factor
        rows = db.cursor().execute(
            f"""WITH zone_year AS (
                    SELECT CAST(FLOOR(cell_row / {f}.0) AS INTEGER) AS zr,
                           CAST(FLOOR(cell_col / {f}.0) AS INTEGER) AS zc,
                           year, COUNT(*) AS cell_days
                    FROM cell_days
                    WHERE has_modis AND year BETWEEN ? AND ?
                    GROUP BY zr, zc, year
                )
                SELECT zr, zc, COUNT(*) AS n_years, MIN(year), MAX(year)
                FROM zone_year
                WHERE cell_days >= ?
                GROUP BY zr, zc
                HAVING COUNT(*) >= ?""",
            [settings.recurrent_first_year, settings.recurrent_last_year,
             settings.recurrent_min_cell_days, settings.recurrent_min_years],
        ).fetchall()
        self.n_zones = len(rows)

        d = self.zone_deg
        squares = [box(round(zc * d, 6), round(zr * d, 6), round((zc + 1) * d, 6), round((zr + 1) * d, 6))
                   for zr, zc, *_ in rows]
        centers = [Point((zc + 0.5) * d, (zr + 0.5) * d) for zr, zc, *_ in rows]
        merged = shapely.unary_union(squares) if squares else shapely.Polygon()
        polygons = list(getattr(merged, "geoms", [merged])) if not merged.is_empty else []

        center_tree = STRtree(centers) if centers else None
        self.features: list[dict] = []
        for i, poly in enumerate(sorted(polygons, key=lambda p: -p.area)):
            idx = center_tree.query(poly, predicate="contains") if center_tree is not None else []
            members = [rows[j] for j in idx]
            years = [m[2] for m in members]
            self.features.append({
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {
                    "id": i,
                    "n_zones": len(members),
                    "years_active_max": max(years, default=0),
                    "years_active_mean": round(sum(years) / len(years), 1) if years else 0,
                    "first_year": min((m[3] for m in members), default=None),
                    "last_year": max((m[4] for m in members), default=None),
                },
            })
        self._polys = [shapely.geometry.shape(f["geometry"]) for f in self.features]
        self._tree = STRtree(self._polys) if self._polys else None

    @property
    def criteria(self) -> dict:
        s = self.settings
        return {
            "zone_deg": self.zone_deg,
            "min_years": s.recurrent_min_years,
            "min_cell_days_per_year": s.recurrent_min_cell_days,
            "period": [s.recurrent_first_year, s.recurrent_last_year],
            "sensor": "MODIS (Terra + Aqua)",
            "description": (
                f"Zonas de {self.zone_deg}° (~{self.zone_deg * 111:.1f} km) con al menos "
                f"{s.recurrent_min_cell_days} celdas-día de fuego detectadas por MODIS en al menos "
                f"{s.recurrent_min_years} de los años {s.recurrent_first_year}-{s.recurrent_last_year}."
            ),
        }

    def get(self, bbox: BBox) -> dict:
        if self._tree is None:
            feats = []
        else:
            idx = self._tree.query(box(*bbox), predicate="intersects")
            feats = [self.features[i] for i in sorted(idx)]
        return {
            "type": "FeatureCollection",
            "criteria": self.criteria,
            "total_polygons": len(self.features),
            "features": feats,
        }
