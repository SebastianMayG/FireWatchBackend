"""Indicadores, calendario, tendencia y comparación.

Métricas (ver docs/metodologia_armonizacion.md):
- activity:   Σ peso de cell_days -> actividad armonizada, comparable entre años.
- detections: número de detecciones crudas (todos los sensores) -> lo que se ve en el mapa.
"""
from functools import lru_cache
from statistics import median

from ..bbox import BBox
from ..config import Settings
from ..db import Database


class ActivityService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.years = db.years
        self.complete_years = [y for y in self.years if y not in settings.partial_years]
        # caché por área: el mismo bbox se consulta varias veces (cards, calendario, tendencia, PDF)
        self._annual = lru_cache(maxsize=256)(self._annual_uncached)
        self._monthly = lru_cache(maxsize=256)(self._monthly_uncached)

    # ---------- consultas base ----------
    def _annual_uncached(self, bbox: BBox) -> dict[int, dict]:
        cur = self.db.cursor()
        # activity = Σ peso (armonizada); modis_days / terra_days = celdas-día sin escalar,
        # usadas como base común al comparar años estimados (ver compare()).
        sums = {
            y: (a, m, t) for y, a, m, t in cur.execute(
                """SELECT year, SUM(peso),
                          SUM(CASE WHEN has_modis THEN 1 ELSE 0 END),
                          SUM(CASE WHEN (sensors & 1) > 0 THEN 1 ELSE 0 END)
                   FROM cell_days
                   WHERE lon_c BETWEEN ? AND ? AND lat_c BETWEEN ? AND ?
                   GROUP BY year""",
                [bbox.min_lon, bbox.max_lon, bbox.min_lat, bbox.max_lat],
            ).fetchall()
        }
        det = dict(cur.execute(
            """SELECT year, COUNT(*) FROM hotspots
               WHERE longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?
               GROUP BY year""",
            [bbox.min_lon, bbox.max_lon, bbox.min_lat, bbox.max_lat],
        ).fetchall())
        out = {}
        for y in self.years:
            a, m, t = sums.get(y, (0.0, 0, 0))
            out[y] = {
                "activity": float(a or 0.0),
                "modis_days": int(m or 0),
                "terra_days": int(t or 0),
                "detections": int(det.get(y, 0)),
            }
        return out

    def _monthly_uncached(self, bbox: BBox) -> dict[int, list[float]]:
        rows = self.db.cursor().execute(
            """SELECT year, month, SUM(peso) FROM cell_days
               WHERE lon_c BETWEEN ? AND ? AND lat_c BETWEEN ? AND ?
               GROUP BY year, month""",
            [bbox.min_lon, bbox.max_lon, bbox.min_lat, bbox.max_lat],
        ).fetchall()
        out = {y: [0.0] * 12 for y in self.years}
        for y, m, v in rows:
            if y in out:
                out[y][m - 1] = float(v or 0.0)
        return out

    # ---------- helpers ----------
    def is_estimated(self, year: int) -> bool:
        return year <= self.settings.calibrated_until

    def is_partial(self, year: int) -> bool:
        return year in self.settings.partial_years

    def median_activity(self, bbox: BBox) -> float:
        annual = self._annual(bbox)
        return float(median(annual[y]["activity"] for y in self.complete_years))

    def peak_year(self, bbox: BBox) -> int | None:
        annual = self._annual(bbox)
        best = max(self.complete_years, key=lambda y: annual[y]["activity"])
        return best if annual[best]["activity"] > 0 else None

    @staticmethod
    def pct_change(new: float, base: float) -> float | None:
        return round((new - base) / base * 100, 1) if base > 0 else None

    # ---------- endpoints ----------
    def indicators(self, year: int, bbox: BBox) -> dict:
        annual = self._annual(bbox)
        monthly = self._monthly(bbox)[year]
        med = self.median_activity(bbox)
        act = annual[year]["activity"]
        top = sorted(
            ({"month": i + 1, "activity": round(v, 1)} for i, v in enumerate(monthly) if v > 0),
            key=lambda d: d["activity"], reverse=True,
        )[:3]
        return {
            "year": year,
            "detections": annual[year]["detections"],
            "activity": round(act, 1),
            "peak_year": self.peak_year(bbox),
            "top_months": top,
            "median_activity": round(med, 1),
            "vs_median_pct": self.pct_change(act, med),
            "years_analyzed": len(self.complete_years),
            "estimated": self.is_estimated(year),
            "partial": self.is_partial(year),
        }

    def calendar(self, bbox: BBox) -> dict:
        monthly = self._monthly(bbox)
        values = [[round(v, 1) for v in monthly[y]] for y in self.years]
        return {
            "years": self.years,
            "months": list(range(1, 13)),
            "values": values,
            "max": max((v for row in values for v in row), default=0.0),
            "estimated_years": [y for y in self.years if self.is_estimated(y)],
            "partial_years": [y for y in self.years if self.is_partial(y)],
        }

    def trend(self, bbox: BBox) -> dict:
        annual = self._annual(bbox)
        return {
            "series": [
                {
                    "year": y,
                    "activity": round(annual[y]["activity"], 1),
                    "detections": annual[y]["detections"],
                    "estimated": self.is_estimated(y),
                    "partial": self.is_partial(y),
                }
                for y in self.years
            ],
            "median_activity": round(self.median_activity(bbox), 1),
            "peak_year": self.peak_year(bbox),
        }

    def comparison_basis(self, year_a: int, year_b: int, bbox: BBox) -> dict:
        """Base común para comparar dos años sin que el factor de calibración decida el resultado.

        - Ambos años medidos (>= 2012): actividad armonizada.
        - Alguno solo-Terra (<= terra_only_until, sin Aqua): celdas-día detectadas por Terra.
        - Alguno estimado (<= calibrated_until): celdas-día detectadas por MODIS (Terra + Aqua).
        Los valores sin escalar solo sirven para comparar entre sí, no con la actividad armonizada.
        """
        s = self.settings
        annual = self._annual(bbox)
        oldest = min(year_a, year_b)
        if oldest <= s.terra_only_until:
            metric, key = "terra_cell_days", "terra_days"
        elif oldest <= s.calibrated_until:
            metric, key = "modis_cell_days", "modis_days"
        else:
            metric, key = "activity", "activity"
        va, vb = annual[year_a][key], annual[year_b][key]
        if year_a == year_b or va == vb:
            peak = sorted({year_a, year_b}) if va > 0 else []
        else:
            peak = [year_a if va > vb else year_b]
        min_det = min(annual[year_a]["detections"], annual[year_b]["detections"])
        return {
            "metric": metric,
            "a": round(float(va), 1),
            "b": round(float(vb), 1),
            "pct_b_vs_a": self.pct_change(vb, va),
            "pct_a_vs_b": self.pct_change(va, vb),
            "peak_years": peak,
            "low_data": min_det < s.low_data_detections,
            "low_data_threshold": s.low_data_detections,
        }

    def compare(self, year_a: int, year_b: int, bbox: BBox) -> dict:
        a = self.indicators(year_a, bbox)
        b = self.indicators(year_b, bbox)
        return {
            "a": a,
            "b": b,
            "basis": self.comparison_basis(year_a, year_b, bbox),
            "delta": {
                "activity_pct": self.pct_change(b["activity"], a["activity"]),
                "detections_pct": self.pct_change(b["detections"], a["detections"]),
                "activity_abs": round(b["activity"] - a["activity"], 1),
                "detections_abs": b["detections"] - a["detections"],
            },
        }
