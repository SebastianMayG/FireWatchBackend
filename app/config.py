from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

ATTRIBUTION = (
    "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource "
    "Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere "
    "Near real-time Capability for EO (LANCE) and NASA's Earth Science Data and Information System (ESDIS)."
)


class Settings(BaseSettings):
    """Configuración; cualquier campo se puede sobrescribir con una variable de entorno o con .env."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    data_dir: Path = ROOT / "data_processed"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Área por defecto (México completo): minLon, minLat, maxLon, maxLat
    default_bbox: tuple[float, float, float, float] = (-118.5, 14.0, -86.0, 33.5)

    # Mapa: máximo de puntos reales antes de cambiar a rejilla agregada
    points_limit: int = 20_000
    grid_sizes: tuple[float, ...] = (0.01, 0.02, 0.05, 0.1, 0.25)

    # Zonas recurrentes
    zone_factor: int = 5  # celdas de 0.01° por lado de zona -> 0.05°
    recurrent_min_years: int = 15
    recurrent_min_cell_days: int = 5  # celdas-día MODIS mínimas en la zona para contar un año como activo
    recurrent_first_year: int = 2001
    recurrent_last_year: int = 2025

    # Años
    partial_years: tuple[int, ...] = (2000,)
    calibrated_until: int = 2011  # años <= a este dependen del factor de calibración
    terra_only_until: int = 2002  # años <= a este tuvieron meses solo con Terra (Aqua desde 2002-07-04)
    low_data_detections: int = 30  # menos detecciones en alguno de los años -> comparación poco confiable

    # Azure (opcional, solo para scripts/sync_from_azure.py)
    azure_storage_connection_string: str | None = None
    azure_container: str = "firms-data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
