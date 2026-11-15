"""Datos sintéticos pequeños con valores conocidos para probar la API sin los 200 MB reales.

Diseño:
- Años 2000-2025 (2000 parcial). Cada año completo tiene 10 celdas-día con peso 1 en la
  "zona de fondo"; 2005 tiene 50 (año pico). 2000 tiene 1000 para comprobar que se excluye.
- Zona recurrente: 5 celdas-día MODIS por año durante 16 años (2001-2016) -> SÍ recurrente.
- Zona débil: 4 celdas-día por año los 25 años -> NO (no llega al mínimo de celdas-día).
- Zona corta: 5 celdas-día por año solo 14 años -> NO (no llega al mínimo de años).
- hotspots 2020: 8 puntos en Tierra Caliente (3 de confianza alta) + 30 puntos dispersos.
"""
import json
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

YEARS = list(range(2000, 2026))
GRID = 0.01

# filas/columnas de celdas de 0.01° (lat = row*0.01, lon = col*0.01)
BACKGROUND = (2500, -10500)   # 25.00 N, -105.00
RECURRENT = (1900, -10000)    # 19.00 N, -100.00  (zona 380, -2000)
WEAK = (2000, -9900)          # 20.00 N, -99.00
SHORT = (2100, -9800)         # 21.00 N, -98.00


def _cell_day(row, col, d: date, peso=1.0, sensors=3):
    return {
        "cell_id": row * 100_000 + col + 50_000, "date": pd.Timestamp(d), "n_det": 1,
        "frp_max": 10.0, "frp_sum": 10.0, "cell_row": row, "cell_col": col,
        "sensors": sensors, "year": d.year, "month": d.month,
        "lat_c": (row + 0.5) * GRID, "lon_c": (col + 0.5) * GRID,
        "has_modis": bool(sensors & 3), "has_base": bool(sensors & 7), "peso": peso,
    }


def build_cell_days() -> pd.DataFrame:
    rows = []
    for y in YEARS:
        n = 1000 if y == 2000 else (50 if y == 2005 else 10)
        month = 12 if y == 2000 else 4  # fondo en abril
        for i in range(n):
            rows.append(_cell_day(BACKGROUND[0] + i % 5, BACKGROUND[1], date(y, month, 1) + timedelta(days=i % 28)))
        if y == 2025:  # algo de actividad en mayo para probar top_months
            rows += [_cell_day(BACKGROUND[0], BACKGROUND[1] + 1, date(y, 5, d)) for d in range(1, 4)]

    def zone(base, years, per_year):
        for y in years:
            for i in range(per_year):  # celdas distintas dentro de la misma zona de 5x5
                rows.append(_cell_day(base[0] + i % 5, base[1] + i // 5, date(y, 3, 10), peso=0.0))

    zone(RECURRENT, range(2001, 2017), 5)
    zone(WEAK, range(2001, 2026), 4)
    zone(SHORT, range(2001, 2015), 5)
    return pd.DataFrame(rows)


def build_hotspots() -> pd.DataFrame:
    pts = []
    for i in range(8):
        pts.append((18.5 + i * 0.01, -101.35, "high" if i < 3 else "nominal"))
    for i in range(30):
        pts.append((16 + i * 0.5, -110 + i * 0.7, "low"))
    rows = []
    for k, (lat, lon, conf) in enumerate(pts):
        dt = datetime(2020, 4, 1, 19, 30) + timedelta(hours=k)
        rows.append({
            "latitude": lat, "longitude": lon, "datetime_utc": pd.Timestamp(dt, tz="UTC"),
            "date": pd.Timestamp(dt.date()), "month": 4, "satellite": "SNPP", "sensor": "VIIRS",
            "conf_level": conf, "frp": 5.0 + k, "bright_main": 330.0, "bright_secondary": 295.0,
            "daynight": "D", "cell_id": 0, "year": 2020,
        })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("data_processed")
    build_cell_days().to_parquet(d / "cell_days.parquet", index=False)
    build_hotspots().to_parquet(d / "hotspots", partition_cols=["year"], index=False)
    (d / "meta.json").write_text(json.dumps({
        "years": YEARS, "default_year": 2025, "sensors": ["MODIS Terra", "MODIS Aqua", "VIIRS S-NPP", "VIIRS NOAA-20"],
        "partial_years": [2000]}))
    (d / "calibration_factors.json").write_text(json.dumps({"grid_deg": GRID, "R_mes": {}, "A_mes": {}}))
    (d / "quality_report.json").write_text(json.dumps({"limpieza": {"duplicados_exactos": 4}}))
    return d


@pytest.fixture(scope="session")
def client(data_dir):
    settings = Settings(data_dir=data_dir, points_limit=10)
    with TestClient(create_app(settings)) as c:
        yield c
