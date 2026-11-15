# Metodología de limpieza y armonización — FireWatch

Este documento describe cómo se transforman los datos crudos de NASA FIRMS (MODIS y VIIRS, México) en los productos que consume la API. Cada decisión incluye su justificación y su efecto medido. Es la base de la sección *"About the project"* del frontend.

Implementación: [`notebooks/01_limpieza_armonizacion.ipynb`](../notebooks/01_limpieza_armonizacion.ipynb). Las cifras corresponden a [`data_processed/quality_report.json`](../data_processed/quality_report.json) y [`calibration_factors.json`](../data_processed/calibration_factors.json); si se vuelve a correr el notebook, hay que actualizarlas aquí.

---

## 1. Fuentes

Datos de archivo anuales por país de NASA FIRMS, descargados con [`descarga.py`](../descarga.py).

| Serie | Satélite(s) | Resolución | Periodo | Versión en archivo | Filas crudas |
|---|---|---|---|---|---|
| MODIS | Terra (desde nov-2000), Aqua (desde 2002-07-04) | ~1 km | 2000-11-01 → 2025-12-31 | `6.2` (2000–2017), `6.03` (2018–2022), `61.03` (2023–2025) | 1,685,470 |
| VIIRS S-NPP | Suomi NPP | 375 m | 2012-01-20 → 2025-12-31 | `2` | 4,225,823 |
| VIIRS NOAA-20 | NOAA-20 (JPSS-1) | 375 m | 2018-04-01 → 2025-12-31 | `2` | 2,394,833 |
| **Total** | | | | | **8,306,126** |

Las tres versiones de MODIS cubren periodos consecutivos sin traslape, así que no hay registros duplicados entre ellas.

> **Atribución requerida:** "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for EO (LANCE) and NASA's Earth Science Data and Information System (ESDIS)."

---

## 2. Esquema común

- Columnas de brillo unificadas: `brightness`/`bright_ti4` → `bright_main`; `bright_t31`/`bright_ti5` → `bright_secondary`.
- Satélites normalizados: `Terra`, `Aqua`, `SNPP` (antes `N`), `NOAA20` (antes `N20`).
- `datetime_utc` = `acq_date` + `acq_time` (HHMM, UTC).
- **Confianza** normalizada a `conf_level` ∈ {`low`, `nominal`, `high`}:
  - VIIRS: `l`/`n`/`h` directamente ([atributos FIRMS](https://earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs)).
  - MODIS (0–100): `<30` low, `30–79` nominal, `≥80` high, según los cortes de la guía de usuario de MODIS Collection 6. La página de atributos de FIRMS describe las tres clases pero no publica los cortes numéricos.
  - Las detecciones de baja confianza **se conservan** y se marcan, para que la API decida si filtrarlas.

---

## 3. Limpieza

| Paso | Criterio | Filas eliminadas |
|---|---|---|
| Duplicados exactos | misma lat, lon, fecha-hora y satélite | 4 |
| Fuera de México | fuera de lat 14–33.5, lon −118.5 a −86 | 0 |
| Confianza inválida | sin valor interpretable | 0 |
| NRT con estándar disponible | versión NRT en fechas con versión estándar | 0 |
| No vegetación (`type ≠ 0`) | ver §4 | 904,465 |
| VIIRS en máscara de fuentes fijas | ver §4 | 121,124 |
| Persistencia (fuentes fijas residuales) | ver §4.3 | 38,555 |
| **Detecciones limpias** | | **7,241,978** |

Detecciones limpias por satélite: S-NPP 3,640,154 · NOAA-20 2,051,358 · Aqua 819,444 · Terra 731,022.

---

## 4. Separar incendios de otras fuentes de calor

FIRMS detecta **cualquier anomalía térmica**, no solo incendios. Volcanes, refinerías, quemadores de gas y plataformas petroleras aparecen igual que un incendio. Si no se quitan, se convierten en falsas "zonas de incendio recurrente", porque arden todos los días del año.

### 4.1 Campo `type` de FIRMS

Según la [documentación de atributos de FIRMS](https://earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs), el *inferred hot spot type* vale `0` = incendio de vegetación presunto, `1` = volcán activo, `2` = otra fuente terrestre estática, `3` = offshore. Se conservan solo los `type = 0`.

Se verificó visualmente: los `type=1` caen sobre el Popocatépetl y el Volcán de Colima, los `type=3` frente a Campeche y los `type=2` en zonas petroleras e industriales.

### 4.2 Máscara de fuentes fijas (bug de VIIRS versión 2)

FIRMS [reportó](https://firms.modaps.eosdis.nasa.gov/content/notifications/firms/news.html) un error en los archivos VIIRS de versiones 1 y 2: el campo `type` se asignó de forma inconsistente, y muchas fuentes industriales (`type=2`) quedaron marcadas como vegetación (`type=0`). Se corrigió en la versión 3 (mayo 2025). **Nuestros datos VIIRS son versión 2.**

Mitigación: el `type` de MODIS sí es confiable, así que se toman todas las celdas de 1 km donde MODIS registró `type ∈ {1, 2, 3}` en cualquier año, se amplían una celda en cada dirección (vecindad 3×3, ~3 km) y se descartan las detecciones VIIRS dentro de esa máscara.

- Celdas en la máscara: **17,312**
- Detecciones VIIRS eliminadas: **121,124**

### 4.3 Filtro de persistencia (fuentes residuales)

Aun después de la máscara, las celdas más activas del registro resultaron ser instalaciones de CFE, Pemex y quemadores de gas, verificadas manualmente en imagen satelital. MODIS no las marcó porque son fuentes pequeñas o recientes, que solo VIIRS alcanza a ver.

Una fuente industrial se distingue de un incendio por su patrón temporal. En México los incendios se concentran en marzo–mayo y casi desaparecen con las lluvias: antes de este filtro, solo **6.2%** de las celdas-día nacionales caían en julio–octubre, mientras que en las 50 celdas más activas esa proporción subía a **35%**.

Criterio: una celda de 1 km se marca como fuente fija si cumple **las tres** condiciones:
1. ≥ 100 días activos en todo el registro,
2. actividad en ≥ 10 de los 12 meses del año,
3. ≥ 15% de sus días activos en julio–octubre.

Resultado: **171 celdas** marcadas y **38,555 detecciones** eliminadas. Se exportan en `static_mask.parquet` con `motivo = "persistencia"`, mientras que las de §4.2 llevan `motivo = "modis_type_1_2_3"`.

El criterio es conservador a propósito: deja intactas zonas de quema recurrente reales. Tras aplicarlo, las celdas más activas del registro son de la Tierra Caliente de Michoacán (18.49°N, 101.36°W: 257 días en 24 años, concentrados en 3 meses al año), un patrón típico de incendio y no de industria.

---

## 5. Armonización

### 5.1 El problema

MODIS (1 km) y VIIRS (375 m) no son comparables por número de puntos. VIIRS detecta incendios más pequeños, y un solo incendio genera varios píxeles VIIRS por cada píxel MODIS. Si solo se suman los puntos, el número de detecciones parece multiplicarse en 2012 (llega S-NPP) y otra vez en 2018 (llega NOAA-20), sin que haya más incendios.

### 5.2 Unidad común: celda-día de 1 km

- Rejilla regular de **0.01°** (~1.1 km, cercano a la resolución de MODIS).
- Una **celda-día** cuenta como activa si **al menos un sensor** detectó fuego en esa celda ese día.
- Así se eliminan los duplicados entre sensores y entre píxeles VIIRS vecinos: 10 píxeles VIIRS y 1 MODIS del mismo incendio, en la misma celda y el mismo día, cuentan como **1**.
- Resultado: **4,237,181 celdas-día** en **714,599 celdas** distintas.

### 5.3 Serie base consistente: MODIS ∪ VIIRS S-NPP

La serie de indicadores usa **MODIS + S-NPP**. NOAA-20 se excluye de los indicadores porque su llegada en 2018 crearía un salto artificial, aunque se conserva en los puntos del mapa. Así la serie es homogénea de 2012 a 2025.

### 5.4 Calibración del periodo solo-MODIS (2000–2011)

Antes de 2012 solo existe MODIS. Para que esos años sean comparables con la serie base, se calcula en el periodo de traslape (2012–2025) cuántas celdas-día ve la serie base por cada celda-día que ve MODIS solo:

**R(mes) = celdas-día(MODIS ∪ S-NPP) / celdas-día(MODIS)**

| Mes | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R | 3.38 | 3.76 | 3.54 | 3.27 | 3.57 | 4.18 | 4.12 | 3.76 | 3.40 | 3.84 | 4.08 | 3.53 |

**Estabilidad:** el R anual va de 3.21 a 3.80 (2012–2025) y el coeficiente de variación por mes entre años es de 5–15%. La relación es estable, lo que justifica aplicar un factor fijo.

**Ausencia de Aqua (nov-2000 → 2002-07-03):** en ese periodo solo existe Terra. Se aplica además un factor A(mes) = celdas-día(Terra ∪ Aqua) / celdas-día(Terra), calculado en 2003–2011:

| Mes | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 2.54 | 2.46 | 2.54 | 2.17 | 2.07 | 2.07 | 2.12 | 2.15 | 2.02 | 2.11 | 2.34 | 2.60 |

### 5.5 Peso por celda-día

Cada celda-día lleva un `peso` que resume la armonización:

| Periodo | Celda-día | `peso` |
|---|---|---|
| 2012–2025 | detectada por MODIS o S-NPP | 1 |
| 2012–2025 | detectada solo por NOAA-20 | 0 |
| 2002-07-04 → 2011 | detectada por MODIS | R(mes) |
| 2000-11 → 2002-07-03 | detectada por Terra | R(mes) × A(mes) |

**Actividad armonizada** de cualquier área y periodo = Σ `peso`. Por eso el backend no repite la lógica: filtra por bbox y fechas, y suma.

### 5.6 Validación

- La serie armonizada no presenta escalones en 2012 ni en 2018, a diferencia de la suma de todos los sensores (que sube de ~95 mil a ~210 mil celdas-día en 2012 y a ~382 mil en 2019).
- El calendario reproduce la temporada de incendios conocida en México: pico en abril–mayo y mínimo en julio–octubre.
- Los máximos históricos coinciden con temporadas extremas documentadas. En la serie armonizada, 2011 es el año más alto (339,669), seguido de 2005 (287,560) y 2003 (270,639).

---

## 6. Zonas de incendios recurrentes

Se calculan en la API al arrancar ([`app/services/recurrent.py`](../app/services/recurrent.py)) a partir de `cell_days.parquet`.

- **Zona:** cuadro de 0.05° (~5.6 km), formado por 5 × 5 celdas de 1 km.
- **Año activo:** la zona tuvo **≥ 5 celdas-día** con fuego detectado por MODIS en ese año.
- **Zona recurrente:** tiene **≥ 15 años activos** de los 25 años completos (2001–2025).
- Las zonas recurrentes vecinas se unen en polígonos.

**Por qué solo MODIS:** es el único sensor disponible los 25 años. Si se usara VIIRS, una zona tendría más probabilidad de parecer recurrente después de 2012 solo por la mayor sensibilidad del sensor.

**Por qué exigir 5 celdas-día por año:** con el criterio inicial (≥ 10 años con al menos 1 detección), el 28% de México (~545 mil km²) resultaba "recurrente", con dos manchas de ~200 mil km² cada una. Eso no distingue focos crónicos de zonas donde simplemente hay algún fuego casi cada año. Se compararon varios umbrales:

| Criterio | Zonas | Superficie aprox. | Polígono más grande |
|---|---|---|---|
| ≥ 1 celda-día en ≥ 10 años | 18,179 | 545 mil km² | 6,973 zonas |
| ≥ 3 celdas-día en ≥ 15 años | 3,559 | 107 mil km² | 543 zonas |
| ≥ 2 celdas-día en ≥ 20 años | 2,755 | 83 mil km² | 403 zonas |
| **≥ 5 celdas-día en ≥ 15 años (elegido)** | **1,112** | **33 mil km² (1.7% de México)** | **145 zonas** |

**Resultado:** 369 polígonos. Los umbrales se pueden ajustar con las variables `RECURRENT_MIN_YEARS` y `RECURRENT_MIN_CELL_DAYS`.

**Limitación:** 9 de las 171 celdas eliminadas por el filtro de persistencia (§4.3) quedan dentro de alguna zona recurrente. Esas celdas ya no aportan datos; la zona existe por los incendios de las celdas vecinas.

---

## 7. Productos generados (`data_processed/`)

| Archivo | Contenido | Uso en la API |
|---|---|---|
| `hotspots/year=YYYY/` | detecciones limpias (lat, lon, fecha-hora, satélite, confianza, FRP, `cell_id`) | puntos del mapa, exportación CSV |
| `cell_days.parquet` | una fila por celda-día con `peso`, `sensors` (bitmask Terra=1, Aqua=2, SNPP=4, NOAA20=8), `n_det`, FRP | indicadores, calendario, tendencia, comparación, zonas recurrentes |
| `static_mask.parquet` | celdas excluidas por fuente fija | transparencia y depuración |
| `calibration_factors.json` | R(mes), A(mes), fecha de inicio de Aqua | documentación y "About" |
| `quality_report.json` | filas eliminadas por paso | documentación y "About" |
| `meta.json` | años disponibles, año por defecto, sensores, años parciales | `GET /meta` |

---

## 8. Limitaciones

1. **2000 es parcial** (solo noviembre–diciembre). Se excluye de la mediana histórica y del "año con mayor actividad".
2. **2000–2011 dependen de un factor de calibración.** R se asume constante en el tiempo. Su variación observada (±5–15%) es una medida de la incertidumbre de esos años. En 2000–2002 el multiplicador combinado R × A es de ~7–9, así que la incertidumbre es mayor.
3. **El factor es nacional.** En áreas pequeñas, la relación MODIS/VIIRS puede diferir del promedio nacional, y con pocas detecciones el multiplicador (×3.5, o hasta ×9 en 2000-2002) puede decidir qué año "tuvo más" fuego. **Mitigación en la API:** al comparar dos años, `/compare` devuelve `basis`, una métrica común sin escalar: actividad armonizada si ambos años son ≥ 2012, celdas-día MODIS si alguno es de 2003-2011, y celdas-día Terra si alguno es de 2000-2002. Además marca `low_data` cuando alguno de los años tiene menos de 30 detecciones.
4. **Fechas en UTC.** México está en UTC−6 a UTC−8, así que algunas detecciones nocturnas quedan asignadas al día siguiente. El efecto en los totales mensuales es mínimo.
5. **No se distingue tipo de incendio.** Incendios forestales, quemas agrícolas y quemas de pastizal cuentan igual.
6. **Versiones mixtas de MODIS** (`6.2`, `6.03`, `61.03`) a lo largo del registro, tal como las distribuye FIRMS. No se aplicó corrección entre versiones.
7. **VIIRS versión 2** tiene el error del campo `type`. La máscara y el filtro de persistencia lo mitigan, pero pueden quedar fuentes industriales pequeñas. Se revisaron las celdas más activas que no alcanzan los umbrales (~140–150 días): 17.49°N 93.37°W (Tabasco/Chiapas, pico en 2019), 17.95°N 94.29°W (sur de Veracruz, pico en 2024–2025) y 16.55°N 95.14°W (Istmo, en aumento desde 2012). Las tres se concentran en la temporada seca (nov–may), un patrón de quema y no de fuente industrial. La de Veracruz es la más dudosa: solo la detecta VIIRS, con FRP muy bajo (~0.8 MW), y aparece de golpe en 2024. Podría ser quema de caña o una fuente pequeña nueva, y requiere verificación en imagen satelital. Sería recomendable migrar a la versión 3 cuando esté disponible en los archivos por país.
8. **Deriva orbital de Terra** en sus últimos años de operación, que cambia su hora de paso y puede afectar ligeramente la detección.
9. **Una detección no es un incendio.** Un incendio grande ocupa muchas celdas-día y varios incendios pequeños pueden caer en la misma. La métrica mide **actividad de fuego**, no número de incendios ni área quemada.
