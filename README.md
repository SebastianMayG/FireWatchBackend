# FireWatchBackend

API (FastAPI) del proyecto **FireWatch** (NASA Space Apps Challenge): análisis histórico de puntos calientes en México con datos armonizados de MODIS y VIIRS (NASA FIRMS).

- Contrato de la API: [docs/api.md](docs/api.md)
- Metodología de limpieza y armonización: [docs/metodologia_armonizacion.md](docs/metodologia_armonizacion.md)

## Instalación

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt            # API y tests
pip install -r requirements-notebook.txt   # solo si vas a correr el notebook
```

## Datos

La API lee `data_processed/`, que no se sube a git. Hay dos formas de obtenerla:

1. **Generarla:** descarga los CSV crudos con `python descarga.py` (quedan en `data_NASA_2026/`) y corre `notebooks/01_limpieza_armonizacion.ipynb`.
2. **Descargarla de Azure:** pon `AZURE_STORAGE_CONNECTION_STRING` y `AZURE_CONTAINER` en `.env` y corre `python scripts/sync_from_azure.py`.

## Correr la API

```powershell
uvicorn app.main:app --reload
```
- Documentación interactiva: http://127.0.0.1:8000/docs
- Ejemplo: http://127.0.0.1:8000/indicators?year=2025&bbox=-101.5,18.4,-101.2,18.6

## Configuración (`.env`)

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATA_DIR` | `data_processed` | Carpeta con los datos procesados |
| `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Orígenes del frontend (lista JSON) |
| `POINTS_LIMIT` | `20000` | Máximo de puntos antes de agregar en rejilla |
| `RECURRENT_MIN_YEARS` / `RECURRENT_MIN_CELL_DAYS` | `15` / `5` | Criterio de zonas recurrentes |
| `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_CONTAINER` | — / `firms-data` | Solo para `scripts/sync_from_azure.py` |

## Tests

```powershell
pytest
```
Los tests usan datos sintéticos pequeños (`tests/conftest.py`), así que no necesitan `data_processed/`.

## Estructura

```
app/
  main.py          # crea la app, CORS, carga de datos al arrancar
  config.py        # configuración (variables de entorno / .env)
  db.py            # DuckDB sobre los Parquet
  bbox.py, deps.py # validación de parámetros
  schemas.py       # modelos de respuesta (OpenAPI)
  services/        # lógica: activity (indicadores, calendario, tendencia, comparación), hotspots, recurrent
  routers/         # endpoints
notebooks/         # limpieza y armonización
scripts/           # utilidades (sync con Azure)
tests/
```

## Atribución

"We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for EO (LANCE) and NASA's Earth Science Data and Information System (ESDIS)."
