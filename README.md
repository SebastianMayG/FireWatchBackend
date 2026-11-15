# FireWatch — Backend

FastAPI service for **FireWatch** (NASA Space Apps Challenge): historical analysis of fire hotspots in **Mexico** (~2000 to today) using harmonized **MODIS** and **VIIRS** data from NASA FIRMS.

**Live demo: https://www.firewatch.study/** · Frontend: [FireWatchFrontend](https://github.com/SebastianMayG/FireWatchFrontend)

The backend cleans and harmonizes the raw FIRMS detections and serves everything the frontend needs already processed: hotspots, recurrent zones, indicators, calendar, trend, year comparison and CSV export.

- API contract: [docs/api.md](docs/api.md)
- Cleaning and harmonization methodology: [docs/metodologia_armonizacion.md](docs/metodologia_armonizacion.md) (Spanish)

## Stack

FastAPI + Uvicorn, DuckDB over Parquet files, pandas / pyarrow, Shapely (recurrent-zone polygons), pydantic-settings.

## Installation

Requires Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt            # API and tests
pip install -r requirements-notebook.txt   # only if you will run the notebook
```

## Data

The API reads `data_processed/`, which is not committed to git. There are two ways to get it:

1. **Generate it:** download the raw CSVs with `python descarga.py` (saved to `data_NASA_2026/`) and run `notebooks/01_limpieza_armonizacion.ipynb`.
2. **Download it from Azure:** set `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_CONTAINER` in `.env` and run `python scripts/sync_from_azure.py`.

## Running the API

```powershell
uvicorn app.main:app --reload
```

- Interactive docs (Swagger): http://127.0.0.1:8000/docs
- Example: http://127.0.0.1:8000/indicators?year=2025&bbox=-101.5,18.4,-101.2,18.6

## Endpoints

The area is always sent as a rectangular bounding box: `bbox=minLon,minLat,maxLon,maxLat` (WGS84, longitude first; defaults to all of Mexico). Full details in [docs/api.md](docs/api.md).

| Endpoint | Description |
|---|---|
| `GET /health` | Service status |
| `GET /meta` | Available years, sensors, criteria and attribution |
| `GET /hotspots` | Hotspots for a year and area (raw points, or an aggregated grid when there are too many) |
| `GET /recurrent-zones` | Recurrent wildfire zone polygons (GeoJSON) |
| `GET /indicators` | Key indicators for a year and area |
| `GET /calendar` | Years × months activity matrix |
| `GET /trend` | Annual activity series |
| `GET /compare` | Compares two years for the same area |
| `GET /report` | Everything the PDF report needs, in one call |
| `GET /export/csv` | CSV download of the detections for a year and area |

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `data_processed` | Folder with the processed data |
| `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed frontend origins (JSON list) |
| `POINTS_LIMIT` | `20000` | Max points before aggregating into a grid |
| `RECURRENT_MIN_YEARS` / `RECURRENT_MIN_CELL_DAYS` | `15` / `5` | Recurrent-zone criteria |
| `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_CONTAINER` | — / `firms-data` | Only for `scripts/sync_from_azure.py` |

## Tests

```powershell
pytest
```

Tests use small synthetic data (`tests/conftest.py`), so they don't need `data_processed/`.

## Deployment

The API is deployed to **Azure Container Apps** using the `Dockerfile`. The image includes `data_processed/`, so get the data (see [Data](#data)) before building:

```powershell
docker build -t firewatch-backend .
docker run -p 8000:8000 firewatch-backend
```

The image sets `CORS_ORIGINS` to the production frontend (`https://firewatch.study`, `https://www.firewatch.study`). Override it with `-e CORS_ORIGINS=...` to run it against another origin.

## Project structure

```
app/
  main.py          # app creation, CORS, data loading on startup
  config.py        # settings (environment variables / .env)
  db.py            # DuckDB over the Parquet files
  bbox.py, deps.py # parameter validation
  schemas.py       # response models (OpenAPI)
  services/        # logic: activity (indicators, calendar, trend, comparison), hotspots, recurrent
  routers/         # endpoints (analysis, maps, meta)
notebooks/         # cleaning and harmonization
scripts/           # utilities (Azure sync)
tests/
descarga.py        # raw FIRMS data download
Dockerfile         # production image (Azure Container Apps)
```

## Acknowledgment

We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for EO (LANCE) and NASA's Earth Science Data and Information System (ESDIS).
