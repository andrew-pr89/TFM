"""
Servicio de cálculo de distancias entre ciudades y direcciones.

Usa Nominatim (OpenStreetMap) para geocodificar y haversine para la distancia.
Sin API key requerida.
"""

import logging
import math
import re
import time
from functools import lru_cache

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

log = logging.getLogger(__name__)

_geocoder = Nominatim(user_agent="planet-pulse-tfm/1.0")


def _municipality_of(location) -> str:
    """Extrae el municipio/ciudad real (no la provincia) de un resultado de Nominatim."""
    addr = location.raw.get("address", {})
    return (
        addr.get("city") or addr.get("town") or addr.get("village")
        or addr.get("municipality") or ""
    ).lower()


def _geocode_raw(query: str, expected_city: str | None = None) -> tuple[float, float] | None:
    try:
        time.sleep(1)  # Nominatim exige máx. 1 req/s
        location = _geocoder.geocode(query, language="es", timeout=10, addressdetails=bool(expected_city))
        if location:
            if expected_city:
                # Nombres de calle genéricos (ej. "Gran Via") existen en muchos municipios —
                # comprobar que Nominatim resolvió al MUNICIPIO pedido, no a uno homónimo
                # dentro de la misma provincia (ej. "Barcelona" ciudad vs. provincia).
                resolved_city = _municipality_of(location)
                expected = expected_city.lower()
                if resolved_city and expected not in resolved_city and resolved_city not in expected:
                    log.warning(
                        "[GEO] '%s' resolvió al municipio '%s', se esperaba '%s' — descartando",
                        query, resolved_city, expected_city,
                    )
                    return None
            log.info("[GEO] '%s' → %s (%.4f, %.4f)", query, location.address, location.latitude, location.longitude)
            return (location.latitude, location.longitude)
        log.info("[GEO] '%s' → sin resultado", query)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        log.warning("[GEO] Error geocodificando '%s': %s", query, e)
    return None


_STREET_PREFIXES = re.compile(
    r"\b(calle|calle\.|c/|avda|avda\.|avenida|paseo|plaza|plz|carrer|avinguda|ronda|travessera|"
    r"via|vía|gran vía|boulevard|blvd|rue|strada|strasse|street|st\.|avenue|ave\.)\b",
    re.IGNORECASE,
)


def _is_street_address(address: str) -> bool:
    """Returns True if the address looks like a street-level input (not just a city or POI)."""
    return bool(_STREET_PREFIXES.search(address))


def _without_street_prefix(address: str) -> str | None:
    """
    Devuelve la dirección sin la palabra de tipo de vía inicial (calle/avda/paseo...), o None
    si no hay ninguna. OSM etiqueta cada calle en el idioma cooficial de su región (catalán,
    gallego, euskera...), así que un prefijo en castellano puede no coincidir con los datos
    aunque el nombre propio de la calle sí exista. Quitar el prefijo y dejar que Nominatim
    resuelva por nombre propio + número + ciudad es más robusto que traducir prefijo por
    prefijo (no escala a cada idioma cooficial).
    """
    stripped = _STREET_PREFIXES.sub("", address, count=1)
    stripped = re.sub(r"^[\s,./]+", "", stripped).strip()
    return stripped if stripped and stripped.lower() != address.lower() else None


@lru_cache(maxsize=256)
def _geocode(address: str) -> tuple[float, float] | None:
    """
    Geocodifica una dirección con fallbacks progresivos:
    1. Tal cual
    2. Con ", España" añadido
    3. Solo la ciudad — SOLO si el input NO era ya una dirección de calle
       (para evitar que una calle desconocida resuelva a coordenadas del centro de la ciudad)

    Si la dirección incluye una ciudad explícita (tras la última coma), se valida que
    Nominatim resuelva a ESE municipio y no a uno homónimo dentro de la misma provincia
    (ej. una calle "Gran Via" existe en Barcelona, Sabadell, l'Hospitalet...).
    """
    expected_city = _extract_city(address)

    result = _geocode_raw(address, expected_city=expected_city)
    if result:
        return result

    # Fallback 1: añadir país
    if "españa" not in address.lower() and "spain" not in address.lower():
        result = _geocode_raw(f"{address}, España", expected_city=expected_city)
        if result:
            log.info("[GEO-FB1] Geocodificado con España: '%s'", address)
            return result

    # Fallback sin prefijo de vía: el nombre propio de la calle puede coincidir aunque el
    # prefijo (calle/avda/paseo...) esté en un idioma distinto al de los datos de OSM.
    no_prefix = _without_street_prefix(address)
    if no_prefix:
        result = _geocode_raw(no_prefix, expected_city=expected_city)
        if not result:
            result = _geocode_raw(f"{no_prefix}, España", expected_city=expected_city)
        if result:
            log.info("[GEO-FB-NOPREFIX] Geocodificado sin prefijo de vía: '%s' → '%s'", address, no_prefix)
            return result

    # Fallback 2: usar solo la ciudad — solo para POIs/ciudades, no para calles
    # Si el input contenía un nombre de calle y falló, devolver None para que el sistema
    # pida km al usuario en lugar de devolver coordenadas incorrectas del centro de ciudad.
    if _is_street_address(address):
        log.info("[GEO] Dirección de calle no encontrada, sin fallback a ciudad: '%s'", address)
        return None

    if "," in address:
        city = address.split(",")[-1].strip()
    else:
        city = address.strip().rsplit(" ", 1)[-1]

    if city and city.lower() != address.lower():
        result = _geocode_raw(city)
        if result:
            log.info("[GEO-FB2] Geocodificado por ciudad '%s' desde '%s'", city, address)
            return result

    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _extract_city(address: str) -> str | None:
    """Extrae la ciudad del final de una dirección (último segmento tras coma o última palabra)."""
    last = address.split(",")[-1].strip()
    return last if len(last) >= 3 else None


def is_geocodable(address: str) -> bool:
    """Comprueba si Nominatim puede resolver una dirección (usado para validar direcciones en Ajustes)."""
    return _geocode(address.strip()) is not None


def get_distance_km(origin: str, destination: str) -> float | None:
    coords_o = _geocode(origin.strip())
    coords_d = _geocode(destination.strip())

    if not coords_o:
        log.warning("No se pudo geocodificar origen: '%s'", origin)
        return None
    if not coords_d:
        log.warning("No se pudo geocodificar destino: '%s'", destination)
        return None

    distance = _haversine_km(*coords_o, *coords_d)

    # Si ambas direcciones comparten la misma ciudad y el resultado supera 20 km,
    # Nominatim probablemente geocodificó a un lugar homónimo incorrecto → descartar
    city_o = _extract_city(origin)
    city_d = _extract_city(destination)
    if city_o and city_d and city_o.lower() == city_d.lower() and distance > 20:
        log.warning("Distancia %.0f km sospechosa para misma ciudad '%s' — geocodificación incorrecta, descartando", distance, city_o)
        return None

    log.info("Distancia %s → %s: %.0f km", origin, destination, distance)
    return round(distance, 1)
