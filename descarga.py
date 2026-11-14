"""
Descarga los zips anuales de FIRMS (todos los paises), extrae solo el CSV de
Mexico de cada uno, borra el zip y deja un CSV unido por serie.

Uso:
    python descargar_firms_mexico.py

Resultado:
    datos_mexico/modis_mexico_2000_2025.csv
    datos_mexico/viirs-snpp_mexico_2012_2025.csv
    datos_mexico/viirs-noaa20_mexico_2018_2025.csv

IMPORTANTE: solo la URL de viirs-snpp esta confirmada. Las de MODIS y NOAA-20
siguen el mismo patron pero hay que verificarlas: en la pagina /country/ haz
clic derecho en uno de esos zips, copia el enlace y compara con PLANTILLAS.
Si alguna da 404, corrige la plantilla.
"""
import csv
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://firms.modaps.eosdis.nasa.gov/data/country/zips/"

# serie -> (plantilla del nombre del zip, primer anio, ultimo anio)
PLANTILLAS = {
    "viirs-snpp": ("viirs-snpp_{year}_all_countries.zip", 2012, 2025),   # confirmada
    "viirs-noaa20": ("viirs-jpss1_{year}_all_countries.zip", 2018, 2025),  # confirmada
    "modis": ("modis_{year}_all_countries.zip", 2000, 2025),             # verificar
}

PAIS = "mexico"          # se busca en el nombre de cada archivo dentro del zip
SALIDA = Path("datos_mexico")
TMP = SALIDA / "_tmp"


def descargar(url: str, destino: Path, intentos: int = 3) -> bool:
    for n in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
                while True:
                    bloque = r.read(1024 * 1024)
                    if not bloque:
                        break
                    f.write(bloque)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  404: {url} (revisa la plantilla de URL)")
                return False
            print(f"  HTTP {e.code}, intento {n}/{intentos}")
        except Exception as e:  # red, timeout, etc.
            print(f"  error {e!r}, intento {n}/{intentos}")
        time.sleep(3 * n)
    return False


def extraer_pais(zip_path: Path) -> list[tuple[str, bytes]]:
    """Devuelve [(nombre, contenido)] de los CSV cuyo nombre contenga PAIS."""
    encontrados = []
    with zipfile.ZipFile(zip_path) as z:
        for nombre in z.namelist():
            if nombre.lower().endswith(".csv") and PAIS in nombre.lower():
                encontrados.append((nombre, z.read(nombre)))
    return encontrados


def main() -> int:
    SALIDA.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)

    for serie, (plantilla, y0, y1) in PLANTILLAS.items():
        salida = SALIDA / f"{serie}_mexico_{y0}_{y1}.csv"
        print(f"\n== {serie} ({y0}-{y1}) ==")
        if salida.exists() and salida.stat().st_size > 0:
            print(f"-> ya existe {salida}, se omite (borralo si quieres volver a bajarlo)")
            continue
        encabezado = None
        filas_total = 0
        anios_ok, anios_fallidos = [], []

        with open(salida, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            for year in range(y0, y1 + 1):
                url = BASE + plantilla.format(year=year)
                zpath = TMP / f"{serie}_{year}.zip"
                print(f"{year}: descargando...")
                if not descargar(url, zpath):
                    anios_fallidos.append(year)
                    continue
                try:
                    archivos = extraer_pais(zpath)
                finally:
                    zpath.unlink(missing_ok=True)  # liberar disco

                if not archivos:
                    print(f"  no encontre un CSV con '{PAIS}' en el zip de {year}")
                    anios_fallidos.append(year)
                    continue

                for nombre, contenido in archivos:
                    lector = csv.reader(io.StringIO(contenido.decode("utf-8", "replace")))
                    cab = next(lector, None)
                    if cab is None:
                        continue
                    if encabezado is None:
                        encabezado = cab + ["serie"]
                        writer.writerow(encabezado)
                    elif cab != encabezado[:-1]:
                        print(f"  AVISO: columnas distintas en {nombre}: {cab}")
                    for fila in lector:
                        writer.writerow(fila + [serie])
                        filas_total += 1
                anios_ok.append(year)

        print(f"-> {salida} | filas: {filas_total} | anios ok: {len(anios_ok)}")
        if anios_fallidos:
            print(f"   ANIOS FALLIDOS: {anios_fallidos}")

    try:
        TMP.rmdir()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())