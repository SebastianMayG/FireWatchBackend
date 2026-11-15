"""Puntos calientes para el mapa y exportación CSV.

Un año tiene entre 280 y 600 mil detecciones en México. Para que el mapa responda rápido:
- si el área tiene <= points_limit detecciones -> se envían los puntos reales (GeoJSON);
- si tiene más -> se agregan en una rejilla (la celda más fina que deje <= points_limit celdas).
"""
import csv
import io
from collections.abc import Iterator
from typing import Literal

from ..bbox import BBox
from ..config import Settings
from ..db import Database

MinConf = Literal["low", "nominal", "high"]
_CONF_LEVELS = {"low": ("low", "nominal", "high"), "nominal": ("nominal", "high"), "high": ("high",)}

CSV_COLUMNS = ["latitude", "longitude", "datetime_utc", "date", "satellite", "sensor",
               "conf_level", "frp", "bright_main", "bright_secondary", "daynight"]


def _where(year: int, bbox: BBox, min_conf: MinConf) -> tuple[str, list]:
    levels = _CONF_LEVELS[min_conf]
    sql = (
        "year = ? AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ? "
        f"AND CAST(conf_level AS VARCHAR) IN ({', '.join('?' * len(levels))})"
    )
    return sql, [year, bbox.min_lon, bbox.max_lon, bbox.min_lat, bbox.max_lat, *levels]


class HotspotService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    def get(self, year: int, bbox: BBox, min_conf: MinConf = "low") -> dict:
        where, params = _where(year, bbox, min_conf)
        cur = self.db.cursor()
        total = cur.execute(f"SELECT COUNT(*) FROM hotspots WHERE {where}", params).fetchone()[0]
        base = {"year": year, "bbox": list(bbox), "min_conf": min_conf, "total_detections": int(total)}

        if total <= self.settings.points_limit:
            rows = cur.execute(
                f"""SELECT longitude, latitude, strftime(datetime_utc, '%Y-%m-%dT%H:%M:%SZ'),
                           CAST(satellite AS VARCHAR), CAST(conf_level AS VARCHAR), frp
                    FROM hotspots WHERE {where} ORDER BY datetime_utc""",
                params,
            ).fetchall()
            features = [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"datetime_utc": dt, "satellite": sat, "conf_level": conf, "frp": frp},
                }
                for lon, lat, dt, sat, conf, frp in rows
            ]
            return {**base, "mode": "points", "points": {"type": "FeatureCollection", "features": features}}

        size = self._pick_grid_size(cur, where, params)
        rows = cur.execute(
            f"""SELECT FLOOR(latitude / {size}) AS r, FLOOR(longitude / {size}) AS c,
                       COUNT(*) AS n, MAX(frp) AS frp_max
                FROM hotspots WHERE {where} GROUP BY r, c""",
            params,
        ).fetchall()
        cells = [[round((r + 0.5) * size, 5), round((c + 0.5) * size, 5), int(n), frp_max]
                 for r, c, n, frp_max in rows]
        return {
            **base,
            "mode": "grid",
            "grid": {
                "cell_deg": size,
                "columns": ["lat", "lon", "count", "frp_max"],
                "max_count": max((c[2] for c in cells), default=0),
                "cells": cells,
            },
        }

    def _pick_grid_size(self, cur, where: str, params: list) -> float:
        """La celda más fina con <= points_limit celdas (una sola pasada sobre los datos)."""
        sizes = self.settings.grid_sizes
        exprs = ", ".join(
            f"COUNT(DISTINCT (FLOOR(latitude / {s}), FLOOR(longitude / {s})))" for s in sizes
        )
        counts = cur.execute(f"SELECT {exprs} FROM hotspots WHERE {where}", params).fetchone()
        for s, n in zip(sizes, counts):
            if n <= self.settings.points_limit:
                return s
        return sizes[-1]

    def iter_csv(self, year: int, bbox: BBox, min_conf: MinConf = "low") -> Iterator[str]:
        where, params = _where(year, bbox, min_conf)
        cur = self.db.cursor()
        cur.execute(
            f"""SELECT latitude, longitude, strftime(datetime_utc, '%Y-%m-%dT%H:%M:%SZ'),
                       strftime(date, '%Y-%m-%d'), CAST(satellite AS VARCHAR), CAST(sensor AS VARCHAR),
                       CAST(conf_level AS VARCHAR), frp, bright_main, bright_secondary,
                       CAST(daynight AS VARCHAR)
                FROM hotspots WHERE {where} ORDER BY datetime_utc""",
            params,
        )
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        while True:
            rows = cur.fetchmany(10_000)
            if not rows:
                break
            writer.writerows(rows)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
        if buf.tell():  # sin filas: queda solo el encabezado
            yield buf.getvalue()
