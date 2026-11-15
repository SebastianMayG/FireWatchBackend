"""Descarga los datos procesados desde Azure Blob Storage a DATA_DIR (por defecto data_processed/).

Uso:
    python scripts/sync_from_azure.py            # descarga lo que falte o haya cambiado
    python scripts/sync_from_azure.py --force    # vuelve a descargar todo

Requiere en .env (o como variables de entorno):
    AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
    AZURE_CONTAINER=firms-data
El container debe tener la misma estructura que data_processed/ (cell_days.parquet, hotspots/year=YYYY/..., *.json).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from azure.storage.blob import ContainerClient  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="descargar aunque el archivo ya exista con el mismo tamaño")
    args = parser.parse_args()

    s = get_settings()
    if not s.azure_storage_connection_string:
        print("Falta AZURE_STORAGE_CONNECTION_STRING en .env o en las variables de entorno.")
        return 1

    container = ContainerClient.from_connection_string(s.azure_storage_connection_string, s.azure_container)
    dest = Path(s.data_dir)
    downloaded = skipped = 0
    for blob in container.list_blobs():
        target = dest / blob.name
        if not args.force and target.exists() and target.stat().st_size == blob.size:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"descargando {blob.name} ({blob.size / 1e6:.1f} MB)")
        with open(target, "wb") as f:
            container.download_blob(blob.name).readinto(f)
        downloaded += 1
    print(f"listo: {downloaded} descargados, {skipped} ya estaban al día -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
