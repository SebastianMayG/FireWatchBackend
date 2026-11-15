# FireWatch API — contrato con el frontend

Base URL local: `http://127.0.0.1:8000` · Documentación interactiva (probar endpoints): `/docs`

Todas las respuestas son JSON (salvo el CSV), solo `GET`, con CORS habilitado para el frontend (`CORS_ORIGINS`) y comprimidas con gzip.

## Parámetros comunes

| Parámetro | Formato | Por defecto | Notas |
|---|---|---|---|
| `bbox` | `minLon,minLat,maxLon,maxLat` (WGS84) | México completo | El rectángulo que dibuja el usuario. Orden: **longitud primero**. |
| `year` | entero | el más reciente (`/meta.default_year`) | Debe estar en `/meta.years`. |
| `min_conf` | `low` \| `nominal` \| `high` | `low` (todas) | Solo en `/hotspots` y `/export/csv`. |

Los errores de validación (bbox mal formado, año fuera de rango) responden **422** con `{"detail": "mensaje"}`.

## Dos métricas: no mezclarlas

| Campo | Qué es | Dónde usarlo |
|---|---|---|
| `activity` | **Actividad armonizada**: suma de celdas-día de 1 km con fuego, ponderadas (ver [metodología](metodologia_armonizacion.md)). **Comparable entre años.** | Indicadores, calendario, tendencia, comparaciones, % vs. mediana |
| `detections` | Detecciones crudas de todos los sensores. **No comparable entre años** (VIIRS existe desde 2012 y detecta ~4× más). | Texto "N puntos detectados", mapa y CSV |

Banderas por año: `estimated: true` (2000–2011, valores obtenidos por calibración desde MODIS: conviene mostrarlos con otro estilo o con una nota) y `partial: true` (2000, solo nov–dic).

---

## `GET /meta`
Años disponibles, año por defecto, sensores, criterios de zonas recurrentes, factores de calibración, reporte de calidad y atribución. Conviene llamarlo una vez al cargar la app.
```json
{
  "years": [2000, 2001, "…", 2025],
  "default_year": 2025,
  "complete_years": [2001, "…", 2025],
  "estimated_years": [2000, "…", 2011],
  "partial_years": [2000],
  "sensors": ["MODIS Terra", "MODIS Aqua", "VIIRS S-NPP", "VIIRS NOAA-20"],
  "default_bbox": [-118.5, 14.0, -86.0, 33.5],
  "grid_deg": 0.01,
  "points_limit": 20000,
  "recurrent_zones": {"zone_deg": 0.05, "min_years": 15, "min_cell_days_per_year": 5, "period": [2001, 2025], "description": "…"},
  "calibration": {"R_mes": {"1": 3.38, "…": 0}, "A_mes": {"…": 0}, "first_aqua": "2002-07-04"},
  "quality_report": {"limpieza": {"…": 0}},
  "attribution": "We acknowledge the use of data … FIRMS …"
}
```

## `GET /hotspots?year=&bbox=&min_conf=`
Puntos para el mapa. Según cuántas detecciones haya en el área, responde de dos formas:

**`mode: "points"`** (≤ `points_limit` detecciones): GeoJSON listo para la capa de puntos.
```json
{
  "year": 2025, "bbox": [-101.5, 18.4, -101.2, 18.6], "min_conf": "low",
  "total_detections": 202, "mode": "points",
  "points": {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-101.3975, 18.54419]},
     "properties": {"datetime_utc": "2025-03-27T19:37:00Z", "satellite": "SNPP", "conf_level": "nominal", "frp": 6.86}}
  ]}
}
```

**`mode: "grid"`** (más detecciones): celdas agregadas para pintar como heatmap o círculos proporcionales. `cell_deg` se ajusta solo (0.01° a 0.25°).
```json
{
  "year": 2025, "total_detections": 503801, "mode": "grid",
  "grid": {"cell_deg": 0.1, "columns": ["lat", "lon", "count", "frp_max"], "max_count": 812,
           "cells": [[19.05, -101.35, 120, 45.2], "…"]}
}
```
Al hacer zoom o seleccionar un área más pequeña, se vuelve a pedir con el nuevo `bbox`, y cuando hay pocos puntos llega `points`.

## `GET /recurrent-zones?bbox=`
Polígonos GeoJSON de zonas de incendios recurrentes. No dependen del año. Criterio: zonas de ~5.6 km con al menos 5 celdas-día de fuego MODIS en al menos 15 de los 25 años 2001–2025 (ver `criteria`). Tooltip sugerido: *"This is a recurrent wildfire hotspot zone"*.
```json
{
  "type": "FeatureCollection", "total_polygons": 369, "criteria": {"…": "…"},
  "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": ["…"]},
                "properties": {"id": 0, "n_zones": 145, "years_active_max": 25, "years_active_mean": 18.1,
                               "first_year": 2001, "last_year": 2025}}]
}
```

## `GET /indicators?year=&bbox=`
Datos de las cards.
```json
{
  "year": 2025, "detections": 503801, "activity": 166166.0, "peak_year": 2011,
  "top_months": [{"month": 5, "activity": 59502.0}, {"month": 4, "activity": 39903.0}, {"month": 3, "activity": 20602.0}],
  "median_activity": 208208.0, "vs_median_pct": -20.2, "years_analyzed": 25,
  "estimated": false, "partial": false
}
```
`peak_year` y `vs_median_pct` pueden ser `null` si el área no tiene actividad.

## `GET /calendar?bbox=`
Matriz años × meses para el heatmap. `values[i][j]` es la actividad del año `years[i]` en el mes `months[j]`. El año seleccionado lo resalta el frontend.
```json
{"years": [2000, "…", 2025], "months": [1, "…", 12], "values": [[0, 0, "…"], "…"], "max": 132000.0,
 "estimated_years": [2000, "…", 2011], "partial_years": [2000]}
```

## `GET /trend?bbox=`
```json
{"series": [{"year": 2001, "activity": 179725.4, "detections": 23341, "estimated": true, "partial": false}, "…"],
 "median_activity": 208208.0, "peak_year": 2011}
```

## `GET /compare?year_a=&year_b=&bbox=`
Indicadores de ambos años, en la misma área, y la comparación entre ellos. El calendario es el mismo para ambos lados (`/calendar`), solo cambia el año resaltado.
```json
{"a": {"…indicadores 2008…": 0}, "b": {"…indicadores 2002…": 0},
 "basis": {"metric": "terra_cell_days", "a": 12, "b": 6, "pct_b_vs_a": -50.0, "pct_a_vs_b": 100.0,
           "peak_years": [2008], "low_data": true, "low_data_threshold": 30},
 "delta": {"activity_pct": 28.9, "detections_pct": -52.9, "activity_abs": 13.0, "detections_abs": -9}}
```
**Para comparar los dos años, usar `basis`.** Elige una métrica que ambos años midieron igual, para que el factor de calibración no decida el resultado (en áreas pequeñas, un año anterior a 2012 se multiplica ×3.5, y uno de 2000-2002 hasta ×9):

| Años comparados | `basis.metric` | Qué cuenta |
|---|---|---|
| ambos ≥ 2012 | `activity` | actividad armonizada |
| alguno 2003–2011 | `modis_cell_days` | celdas-día con fuego detectadas por MODIS, sin escalar |
| alguno 2000–2002 | `terra_cell_days` | celdas-día detectadas solo por Terra (único satélite presente en todos los años) |

- `peak_years`: el año con más actividad de los dos (los dos si empatan).
- `low_data: true` cuando alguno de los años tiene menos de `low_data_threshold` detecciones: mostrar un aviso de que la comparación es poco confiable.
- `delta` se conserva por compatibilidad, pero usa la actividad escalada.

## `GET /report?year=&bbox=`
Todo lo necesario para el PDF en una sola llamada: `indicators`, `trend`, `calendar`, `methodology` (texto breve), `attribution` y `bbox`. Si la vista ya tiene esos datos cargados, no hace falta llamarlo.

## `GET /export/csv?year=&bbox=&min_conf=`
Descarga en streaming. Columnas: `latitude, longitude, datetime_utc, date, satellite, sensor, conf_level, frp, bright_main, bright_secondary, daynight`. El header `Content-Disposition` trae el nombre del archivo y `X-Attribution` el texto de atribución de FIRMS (incluirlo en la UI de descarga).

## `GET /health`
`{"status": "ok"}`

---
**Atribución requerida (NASA FIRMS):** "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for EO (LANCE) and NASA's Earth Science Data and Information System (ESDIS)."
