"""Acceso a los datos procesados (Parquet) con DuckDB.

- `cell_days` (4 M filas, ~40 MB) se carga en memoria al arrancar: ahí se calculan
  indicadores, calendario, tendencia y zonas recurrentes.
- `hotspots` (7 M filas) se consulta directo de los Parquet particionados por año;
  DuckDB solo lee la partición del año pedido.
"""
import json
import threading
from pathlib import Path

import duckdb

REQUIRED = ("cell_days.parquet", "hotspots", "meta.json", "calibration_factors.json")


class Database:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        missing = [f for f in REQUIRED if not (self.data_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Faltan archivos en {self.data_dir}: {missing}. Genera los datos con "
                "notebooks/01_limpieza_armonizacion.ipynb o descárgalos con scripts/sync_from_azure.py"
            )

        self.meta: dict = json.loads((self.data_dir / "meta.json").read_text(encoding="utf-8"))
        self.calibration: dict = json.loads((self.data_dir / "calibration_factors.json").read_text(encoding="utf-8"))
        qr = self.data_dir / "quality_report.json"
        self.quality: dict = json.loads(qr.read_text(encoding="utf-8")) if qr.exists() else {}

        self.years: list[int] = sorted(int(y) for y in self.meta["years"])
        self.grid_deg: float = float(self.calibration.get("grid_deg", 0.01))

        self._con = duckdb.connect(database=":memory:")
        self._lock = threading.Lock()
        cd = (self.data_dir / "cell_days.parquet").as_posix()
        hs = (self.data_dir / "hotspots" / "**" / "*.parquet").as_posix()
        self._con.execute(f"""
            CREATE TABLE cell_days AS
            SELECT cell_id, cell_row, cell_col, lat_c, lon_c,
                   CAST(year AS INTEGER) AS year, CAST(month AS INTEGER) AS month,
                   n_det, frp_max, sensors, has_modis, has_base, peso
            FROM read_parquet('{cd}')
        """)
        self._con.execute(f"""
            CREATE VIEW hotspots AS
            SELECT * REPLACE (CAST(year AS INTEGER) AS year)
            FROM read_parquet('{hs}', hive_partitioning = true)
        """)

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Cursor independiente (seguro para usar en paralelo desde varios requests)."""
        with self._lock:
            return self._con.cursor()

    def close(self) -> None:
        self._con.close()
