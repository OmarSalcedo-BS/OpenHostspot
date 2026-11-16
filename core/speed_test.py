"""Estimación de velocidad bajo demanda mediante Cloudflare."""

import time

import requests


DOWNLOAD_URL = "https://speed.cloudflare.com/__down"
UPLOAD_URL = "https://speed.cloudflare.com/__up"
DOWNLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_BYTES = 3 * 1024 * 1024


def measure_speed() -> dict[str, float]:
    """Mide una transferencia en cada dirección; no determina la capacidad máxima."""
    with requests.Session() as session:
        session.trust_env = False
        session.headers["Accept-Encoding"] = "identity"
        start = time.perf_counter()
        with session.get(DOWNLOAD_URL, params={"bytes": DOWNLOAD_BYTES}, stream=True,
                         timeout=(8, 15), allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise RuntimeError(f"Respuesta inesperada de descarga: HTTP {response.status_code}")
            received = 0
            for chunk in response.iter_content(chunk_size=65536):
                if time.perf_counter() - start > 30:
                    raise TimeoutError("La descarga excedió el tiempo máximo de medición.")
                received += len(chunk)
                if received > DOWNLOAD_BYTES:
                    raise RuntimeError("La descarga excedió el tamaño solicitado.")
            if received != DOWNLOAD_BYTES:
                raise RuntimeError(f"Descarga incompleta: {received} de {DOWNLOAD_BYTES} bytes.")
        download_seconds = time.perf_counter() - start

        payload = b"\0" * UPLOAD_BYTES
        start = time.perf_counter()
        with session.post(UPLOAD_URL, data=payload, timeout=(8, 15), allow_redirects=False) as response:
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"Respuesta inesperada de subida: HTTP {response.status_code}")
        upload_seconds = time.perf_counter() - start
    if download_seconds <= 0 or upload_seconds <= 0:
        raise RuntimeError("No se pudo medir la duración de la transferencia.")
    return {
        "download_mbps": DOWNLOAD_BYTES * 8 / download_seconds / 1_000_000,
        "upload_mbps": UPLOAD_BYTES * 8 / upload_seconds / 1_000_000,
    }
