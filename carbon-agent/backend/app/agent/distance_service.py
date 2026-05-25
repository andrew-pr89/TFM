"""
Servicio de cálculo de distancias entre ciudades.

Usa Nominatim (OpenStreetMap) para geocodificar nombres de ciudad
y la fórmula haversine para la distancia de gran círculo.
Sin API key requerida.
"""

import logging
import math
import time
from functools import lru_cache

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

log = logging.getLogger(__name__)

_geocoder = Nominatim(user_agent="carbon-agent-tfm/1.0")


@lru_cache(maxsize=256)
def _geocode(city: str) -> tuple[float, float] | None:
    """Devuelve (lat, lon) para una ciudad, con caché en memoria."""
    try:
        time.sleep(1)  # Nominatim exige máx. 1 req/s
        location = _geocoder.geocode(city, language="es", timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        log.warning("Error geocodificando '%s': %s", city, e)
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo en km entre dos puntos (lat/lon en grados)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_distance_km(origin: str, destination: str) -> float | None:
    """
    Calcula la distancia en km entre dos ciudades usando OpenStreetMap.

    Devuelve None si no se puede geocodificar alguna de las ciudades.
    """
    coords_o = _geocode(origin.strip())
    coords_d = _geocode(destination.strip())

    if not coords_o:
        log.warning("No se pudo geocodificar origen: '%s'", origin)
        return None
    if not coords_d:
        log.warning("No se pudo geocodificar destino: '%s'", destination)
        return None

    distance = _haversine_km(*coords_o, *coords_d)
    log.info("Distancia %s → %s: %.0f km", origin, destination, distance)
    return round(distance, 1)
