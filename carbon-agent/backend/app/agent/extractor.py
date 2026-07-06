"""
Extractor — convierte texto natural en actividades estructuradas.

Orquesta:
  1. Consulta las categorías válidas desde la BD (EmissionFactor)
  2. Llama al LLMService para extraer actividades
  3. Valida y normaliza el resultado antes de devolverlo

El LLM solo identifica qué actividad y cuánta cantidad.
Nunca toca factores de emisión ni hace aritmética.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent.distance_service import get_distance_km
from app.agent.llm_service import LLMService
from app.models.models import EmissionFactor


def _norm(s: str) -> str:
    """Lowercase + strip accents — used for fuzzy category matching."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode("ascii")

log = logging.getLogger(__name__)

# Default portion sizes for non-transport categories (in the factor's native unit).
@dataclass
class ExtractedActivity:
    """Actividad identificada por el LLM, lista para pasar a la Calculadora."""
    category: str
    quantity: float
    unit: str
    description: str
    factor: EmissionFactor  # objeto ORM ya resuelto


class Extractor:
    """Extrae actividades estructuradas de texto libre usando el LLM."""

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    @staticmethod
    def _fuzzy_match_factor(term: str, factors_by_category: dict) -> "EmissionFactor | None":
        """
        Substring fuzzy match: returns the factor whose normalized display_name
        contains the normalized term (or vice-versa). Used as last resort before
        marking an item as unknown.
        """
        norm_term = _norm(term)
        if not norm_term or len(norm_term) < 3:
            return None
        candidates = [
            f for f in factors_by_category.values()
            if norm_term in _norm(f.display_name)
            or (
                _norm(f.display_name) in norm_term
                # Factor display_name must cover ≥60% of the term length to avoid
                # "patatas" (7) matching "tortilla de patatas" (19)
                and len(_norm(f.display_name)) >= len(norm_term) * 0.6
            )
        ]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Prefer the factor whose display_name is closest in length to the term
            return min(candidates, key=lambda f: abs(len(_norm(f.display_name)) - len(norm_term)))
        return None

    def _save_unknown_items(
        self,
        items: list[dict],
        raw_text: str,
        user_id: str,
        db: Session,
    ) -> list[str]:
        """Persists unknown items to the DB. Returns list of term names for the user message."""
        from app.models.models import UnknownItem
        names: list[str] = []
        for item in items:
            term = (item.get("description") or "").strip()
            if not term:
                continue
            existing = (
                db.query(UnknownItem)
                .filter(UnknownItem.raw_term == term, UnknownItem.status == "pending")
                .first()
            )
            if not existing:
                db.add(UnknownItem(
                    user_id=user_id,
                    raw_term=term,
                    context=raw_text,
                    guessed_category=item.get("guessed_type"),
                    status="pending",
                ))
            names.append(term)
        if names:
            db.flush()
            log.info("Unknown items registrados: %s", names)
        return names

    def extract(
        self,
        raw_text: str,
        db: Session,
        home_city: str | None = None,
        work_place: str | None = None,
        commute_km: float | None = None,
        pending_activity: dict | None = None,
        user_portions: dict[str, float] | None = None,
        user_id: str = "default",
        today: str | None = None,
    ) -> list[ExtractedActivity]:
        """
        Extrae actividades del texto y las cruza con los factores de la BD.

        Pasos:
          1. Carga todas las categorías válidas desde emission_factors
          2. Pide al LLM que identifique actividades usando esas categorías
          3. Valida cada actividad: categoría existe, cantidad positiva
          4. Resuelve el EmissionFactor correspondiente
          5. Devuelve lista de ExtractedActivity validadas
        """
        # 1. Categorías válidas desde BD
        factors_by_category: dict[str, EmissionFactor] = {}
        factors_by_norm: dict[str, EmissionFactor] = {}
        for f in db.query(EmissionFactor).all():
            factors_by_category[f.category] = f
            # Index by normalized category AND display_name so the LLM can return either
            factors_by_norm[_norm(f.category)] = f
            factors_by_norm[_norm(f.display_name)] = f

        if not factors_by_category:
            log.error("No hay factores de emisión en la BD — ejecuta init_db primero")
            return []

        # 2. Llamada al LLM — pasamos categoría, nombre legible y unidad
        factors_info = [
            {"category": f.category, "display_name": f.display_name, "unit": f.unit}
            for f in factors_by_category.values()
        ]
        raw_activities = self.llm.extract_activities(
            raw_text=raw_text,
            factors_info=factors_info,
            pending_activity=pending_activity,
            today=today,
            home_city=home_city,
            work_place=work_place,
        )

        log.info("LLM devolvió %d actividades para: '%s'", len(raw_activities), raw_text[:60])
        if raw_activities:
            log.info("Actividades LLM: %s", [
                {"cat": a.get("category"), "qty": a.get("quantity")}
                for a in raw_activities if isinstance(a, dict)
            ])

        # Actividades reales = items con campo "category" (descartamos marcadores puros)
        real_raw_activities = [
            a for a in raw_activities
            if isinstance(a, dict) and a.get("category")
        ]

        if not real_raw_activities:
            log.info("El LLM no identificó actividades con impacto CO₂ en: '%s'", raw_text[:80])
            # Pass through any special markers (clear_pending, etc.) that came back
            marker_items = [a for a in raw_activities if isinstance(a, dict) and not a.get("category")]
            # Fallback: check if message contains unknown food/activity terms worth flagging
            unknown_candidates = self.llm.identify_unknown_items(raw_text)
            if unknown_candidates:
                fuzzy_pending: list[dict] = []
                truly_unknown: list[dict] = []
                for c in unknown_candidates:
                    term = (c.get("term") or "").strip()
                    if not term:
                        continue
                    factor = self._fuzzy_match_factor(term, factors_by_category)
                    if factor:
                        log.info("Fallback fuzzy: '%s' → '%s' (pedirá aclaración)", term, factor.category)
                        _unit_questions: dict[str, str] = {
                            "kg":     f"¿Cuántos gramos de {term} has consumido? (p.ej. 200 para una ración normal)",
                            "litro":  f"¿Cuántos litros de {term}?",
                            "kWh":    f"¿Cuántos kWh de {term}?",
                            "hora":   f"¿Cuántas horas de {term}?",
                            "unidad": f"¿Cuántas unidades de {term}?",
                            "km":     f"¿Cuántos km de {term}?",
                        }
                        question = _unit_questions.get(factor.unit, f"¿Cuánto/a {term} has consumido?")
                        fuzzy_pending.append({
                            "set_pending_activity": {
                                "category": factor.category,
                                "description": term,
                                "question": question,
                            },
                            "clarifying_question": question,
                        })
                    elif c.get("guessed_type") == "transporte":
                        # Transport always has emission factors — only km/route is missing, not a catalog gap
                        log.info("Fallback: ignorando transporte desconocido '%s' (no es ítem de catálogo)", term)
                    else:
                        truly_unknown.append({"category": "unknown", "description": term, "guessed_type": c.get("guessed_type")})

                if fuzzy_pending:
                    unknown_names = self._save_unknown_items(truly_unknown, raw_text, user_id, db) if truly_unknown else []
                    # Return the first pending question (subsequent ones handled in next turns)
                    first = fuzzy_pending[0]
                    pending_data = first["set_pending_activity"]
                    pending_data["question"] = first["clarifying_question"]
                    result_list: list = marker_items + [{"set_pending_activity": pending_data}, {"clarifying_question": first["clarifying_question"]}]
                    if unknown_names:
                        result_list.append({"unknown_items": unknown_names})
                    return result_list  # type: ignore[return-value]

                items_as_unknown = truly_unknown
                names = self._save_unknown_items(items_as_unknown, raw_text, user_id, db)
                if names:
                    return marker_items + [{"unknown_items": names}]  # type: ignore[list-item]
            return marker_items  # type: ignore[return-value]

        # 3 & 4. Validación y resolución — procesar TODAS las actividades
        result: list[ExtractedActivity] = []
        pending_questions: list[str] = []
        unknown_items: list[dict] = []

        _GENERIC_PLACES = {
            "casa", "trabajo", "oficina", "gimnasio", "colegio", "escuela",
            "instituto", "hospital", "mercado", "supermercado", "tienda",
            "universidad", "facultad", "bar", "restaurante", "playa", "campo",
            "hotel", "aeropuerto",
        }

        # Límite de distancia máxima por tipo de transporte (para detectar errores de geocodificación)
        # Metro/taxi: solo urbano. Coche: puede cruzar países enteros.
        _URBAN_TRANSPORT = {"taxi", "moto", "metro", "autobus", "coche_gasolina", "coche_diesel", "coche_electrico"}
        _MAX_KM_BY_CATEGORY: dict[str, float] = {
            "metro":           100.0,   # red urbana
            "taxi":            300.0,   # máximo transfer aeropuerto
            "autobus":        1500.0,   # puede ser interurbano
            "moto":           1500.0,   # puede ser viaje largo
            "coche_gasolina": 3000.0,   # puede cruzar Europa
            "coche_diesel":   3000.0,
            "coche_electrico": 3000.0,
        }

        def _max_km(cat: str) -> float:
            return _MAX_KM_BY_CATEGORY.get(cat, 3000.0)

        # Palabras que indican un POI específico cuya ciudad no se puede inferir con seguridad
        _POI_KEYWORDS = {"hotel", "hostal", "restaurante", "bar", "café", "cafetería", "club", "centro comercial", "estadio", "teatro", "museo"}

        def _is_ambiguous_poi(place: str) -> bool:
            """Devuelve True si el lugar parece un POI con nombre propio sin ciudad explícita."""
            p = place.lower().strip()
            return any(p.startswith(kw) or f" {kw} " in f" {p} " for kw in _POI_KEYWORDS)

        for item in raw_activities:
            # Pasar marcadores especiales sin procesarlos como actividades
            if "set_home_city" in item or "set_activity_date" in item or "clear_pending" in item or ("clarifying_question" in item and not item.get("category")):
                result.append(item)  # type: ignore[arg-type]
                continue

            category = item.get("category", "").strip()

            # El LLM detectó un desplazamiento (origen/destino) pero el usuario no dijo
            # el medio de transporte — preguntar en vez de asumir uno (p.ej. "metro" por defecto).
            if category == "transporte_pendiente":
                origin = (item.get("origin") or "").strip()
                destination = (item.get("destination") or "").strip()
                question = item.get("clarifying_question") or (
                    "¿En qué medio de transporte hiciste ese trayecto? "
                    "(coche, moto, autobús, metro, tren, a pie, bici...)"
                )
                pending_data: dict = {
                    "category": "transporte_pendiente",
                    "description": item.get("description") or "trayecto",
                    "question": question,
                }
                if origin:
                    pending_data["origin"] = origin
                if destination:
                    pending_data["destination"] = destination
                result.append({"set_pending_activity": pending_data, "clarifying_question": question})  # type: ignore[arg-type]
                continue

            # Item marcado como desconocido por el LLM → registrar para revisión
            if category == "unknown":
                # Transport is never a catalog gap — skip silently
                if item.get("guessed_type") == "transporte":
                    log.info("Ignorando transporte con category=unknown (no es ítem de catálogo): %s", item.get("description", ""))
                else:
                    unknown_items.append(item)
                continue
            quantity_raw = item.get("quantity")
            description = item.get("description", category)

            # Validar categoría — si el LLM devuelve una categoría que no existe en la BD,
            # intentar un match normalizado (sin tildes, minúsculas) antes de descartar.
            if category not in factors_by_category:
                fallback = factors_by_norm.get(_norm(category))
                if fallback:
                    log.info("Categoría '%s' resuelta como '%s' por normalización", category, fallback.category)
                    category = fallback.category
                else:
                    log.warning("Categoría '%s' devuelta por LLM no existe en BD — tratando como unknown", category)
                    unknown_items.append({
                        "category": "unknown",
                        "description": description or category,
                        "guessed_type": "otro",
                    })
                    continue

            if quantity_raw is None:
                # Use default portion for non-transport categories before asking the user
                _factor_unit = factors_by_category.get(category, None)
                _is_transport = _factor_unit and _factor_unit.unit == "km"
                _origin_hint = (item.get("origin") or "").strip()
                _dest_hint = (item.get("destination") or "").strip()
                if not _is_transport and not _origin_hint and not _dest_hint:
                    # Priority: user override > factor.default_quantity (DB) > 1 for unidad
                    _default_q = (user_portions or {}).get(category)
                    if _default_q is None and _factor_unit and _factor_unit.default_quantity is not None:
                        _default_q = _factor_unit.default_quantity
                    if _default_q is None and _factor_unit and _factor_unit.unit == "unidad":
                        _default_q = 1.0
                    if _default_q is not None:
                        quantity_raw = _default_q
                        log.info("Usando porción estándar para %s: %s %s", category, _default_q, _factor_unit.unit if _factor_unit else "")

            if quantity_raw is None:
                # Intentar calcular distancia desde ciudades/lugares
                origin = (item.get("origin") or "").strip()
                destination = (item.get("destination") or "").strip()

                def _is_generic(place: str) -> bool:
                    p = place.lower().strip()
                    if "," in p:  # ya tiene ciudad → no genérico
                        return False
                    return p in _GENERIC_PLACES or bool(set(p.split()) & _GENERIC_PLACES)

                # Si hay origen y destino explícitos (dos lugares)
                if origin and destination:
                    origin_generic = _is_generic(origin)
                    dest_generic   = _is_generic(destination)
                    if origin_generic or dest_generic:
                        log.info("Origen/destino genérico ('%s'/'%s') — actividad pendiente", origin, destination)
                        if not origin_generic and dest_generic:
                            # 1. Usar commute_km guardado si existe
                            if commute_km and commute_km > 0:
                                log.info("Usando commute_km guardado: %.1f km", commute_km)
                                quantity_raw = commute_km
                                item["description"] = description + f" ({origin} → {destination}, {commute_km:.1f} km)"
                                description = item["description"]
                                # quantity_raw ya tiene valor → cae al bloque de guardado normal
                            else:
                                # 2. Intentar extraer ciudad del origen y geocodificar
                                city_match = re.search(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\s*$', origin)
                                auto_probed = False
                                if city_match:
                                    city_guess = city_match.group(1)
                                    auto_dest = f"{destination}, {city_guess}"
                                    probe = get_distance_km(origin, auto_dest)
                                    if probe is not None and probe <= _max_km(category):
                                        log.info("Auto-ciudad '%s' → %s → %s: %.0f km", city_guess, origin, auto_dest, probe)
                                        quantity_raw = probe
                                        item["description"] = description + f" ({origin} → {auto_dest}, {probe:.1f} km)"
                                        description = item["description"]
                                        auto_probed = True
                                if not auto_probed:
                                    # 3. Geocoding falló → pedir km, marcar como commute para recordarlo
                                    question = (
                                        f"No pude calcular la distancia a '{destination}' automáticamente. "
                                        f"¿Cuántos km son aproximadamente? Los guardaré para no volver a preguntarte."
                                    )
                                    result.append({  # type: ignore[arg-type]
                                        "set_pending_activity": {"category": category, "description": description, "is_commute": True},
                                        "clarifying_question": question,
                                    })
                                    continue
                        else:
                            question = (
                                f"¿Desde qué lugar exacto y hasta dónde en {description}? "
                                "(p.ej: 'desde la Puerta del Sol, Madrid hasta el estadio Santiago Bernabéu, Madrid')"
                            )
                            result.append({  # type: ignore[arg-type]
                                "set_pending_activity": {"category": category, "description": description},
                                "clarifying_question": question,
                            })
                            continue
                    # POI con nombre propio: intentar geocodificar directamente antes de preguntar ciudad.
                    # Algunos POIs incluyen la ciudad en su nombre (ej: "Hotel Hesperia Madrid") y geocodifican bien.
                    destination_has_city = "," in destination
                    if _is_ambiguous_poi(destination) and category in _URBAN_TRANSPORT and not destination_has_city:
                        probe = get_distance_km(origin, destination)
                        if probe is None or probe > _max_km(category):
                            log.info("Destino POI '%s' no geocodificable sin ciudad — pidiendo ciudad", destination)
                            question = (
                                f"¿En qué ciudad está '{destination}'? "
                                f"Lo necesito para calcular los km de {description}."
                            )
                            result.append({  # type: ignore[arg-type]
                                "set_pending_activity": {"category": category, "description": description, "destination_poi": destination, "origin": origin},
                                "clarifying_question": question,
                            })
                            continue
                        # Geocodificó correctamente — saltar el cálculo normal de abajo
                        quantity_raw = probe
                        item["description"] = description + f" ({origin} → {destination}, {probe:.1f} km)"
                        description = item["description"]
                    else:
                        log.info("[DIST] Calculando distancia %s → %s (commute_km=%s)", origin, destination, commute_km)
                        quantity_raw = get_distance_km(origin, destination)
                        log.info("[DIST] Resultado geocoding: %s km", quantity_raw)
                        if quantity_raw is None or (
                            category in _URBAN_TRANSPORT and quantity_raw > _max_km(category)
                        ):
                            log.info("[DIST] Geocoding falló o fuera de rango — commute_km disponible: %s", commute_km)
                            if commute_km and commute_km > 0:
                                log.info("Geocoding falló, usando commute_km guardado: %.1f km", commute_km)
                                quantity_raw = commute_km
                                item["description"] = description + f" ({origin} → {destination}, {commute_km:.1f} km)"
                                description = item["description"]
                            else:
                                if quantity_raw and quantity_raw > _max_km(category):
                                    log.warning("Distancia %s → %s = %.0f km parece incorrecta para %s", origin, destination, quantity_raw, category)
                                    question = f"No pude calcular bien la distancia para {description}. ¿Cuántos km son aproximadamente? Los guardaré para el futuro."
                                else:
                                    log.warning("No se pudo calcular distancia %s → %s", origin, destination)
                                    question = f"No pude calcular la distancia entre {origin} y {destination}. ¿Cuántos km son aproximadamente? Los guardaré para el futuro."
                                result.append({  # type: ignore[arg-type]
                                    "set_pending_activity": {"category": category, "description": description, "is_commute": True},
                                    "clarifying_question": question,
                                })
                                continue
                        item["description"] = description + f" ({origin} → {destination}, {quantity_raw:.1f} km)"
                        description = item["description"]

                # Solo hay destino — usar home_city como origen si está disponible
                elif destination and not origin:
                    if destination.lower() in _GENERIC_PLACES:
                        question = (
                            f"¿Desde qué lugar exacto y hasta dónde en {description}? "
                            "(p.ej: 'desde la Puerta del Sol, Madrid hasta el estadio Santiago Bernabéu, Madrid')"
                        )
                        result.append({  # type: ignore[arg-type]
                            "set_pending_activity": {"category": category, "description": description},
                            "clarifying_question": question,
                        })
                        continue
                    # POI sin ciudad explícita (sin coma): pedir ciudad antes de intentar geocodificar
                    if _is_ambiguous_poi(destination) and category in _URBAN_TRANSPORT and "," not in destination:
                        question = (
                            f"¿En qué ciudad está '{destination}'? "
                            f"Lo necesito para calcular los km de {description}."
                        )
                        result.append({  # type: ignore[arg-type]
                            "set_pending_activity": {"category": category, "description": description, "destination": destination},
                            "clarifying_question": question,
                        })
                        continue
                    # Para transporte urbano con destino "POI, ciudad":
                    # no usar home_city si es una ciudad distinta al destino
                    dest_city_hint = destination.split(",")[-1].strip() if "," in destination else ""
                    home_city_is_remote = (
                        category in _URBAN_TRANSPORT
                        and dest_city_hint
                        and home_city
                        and home_city.lower() not in dest_city_hint.lower()
                        and dest_city_hint.lower() not in home_city.lower()
                    )

                    if home_city and not home_city_is_remote:
                        log.info("Usando home_city '%s' como origen para → %s", home_city, destination)
                        quantity_raw = get_distance_km(home_city, destination)
                        if quantity_raw is None or (
                            category in _URBAN_TRANSPORT and quantity_raw > _max_km(category)
                        ):
                            if commute_km and commute_km > 0:
                                log.info("Geocoding falló, usando commute_km guardado: %.1f km", commute_km)
                                quantity_raw = commute_km
                                item["description"] = description + f" ({home_city} → {destination}, {commute_km:.1f} km)"
                                description = item["description"]
                            else:
                                if quantity_raw and quantity_raw > _max_km(category):
                                    log.warning("Distancia %s → %s = %.0f km parece incorrecta para %s", home_city, destination, quantity_raw, category)
                                    question = f"No pude calcular bien la distancia para {description}. ¿Cuántos km son aproximadamente? Los guardaré para el futuro."
                                else:
                                    log.warning("No se pudo calcular distancia %s → %s", home_city, destination)
                                    question = f"No pude calcular la distancia entre {home_city} y {destination}. ¿Cuántos km son aproximadamente? Los guardaré para el futuro."
                                result.append({  # type: ignore[arg-type]
                                    "set_pending_activity": {"category": category, "description": description, "destination": destination, "is_commute": True},
                                    "clarifying_question": question,
                                })
                                continue
                        if quantity_raw is not None:
                            item["description"] = description + f" ({home_city} → {destination}, {quantity_raw:.1f} km)"
                            description = item["description"]
                    else:
                        # Sin home_city (o home_city en otra ciudad) — pedir origen local
                        if dest_city_hint and category in _URBAN_TRANSPORT:
                            question = (
                                item.get("clarifying_question")
                                or f"¿Desde dónde cogiste el {description.lower()} en {dest_city_hint}? "
                                   f"(p.ej: 'desde la estación de tren')"
                            )
                        else:
                            question = (
                                item.get("clarifying_question")
                                or "¿Desde qué ciudad saliste? La recordaré para la próxima vez."
                            )
                        result.append({  # type: ignore[arg-type]
                            "set_pending_activity": {"category": category, "description": description, "destination": destination},
                            "clarifying_question": question,
                        })
                        continue

                elif item.get("clarifying_question"):
                    # Actividad de cualquier tipo que necesita más información (cantidad, unidad, etc.)
                    question = item["clarifying_question"]
                    log.info("Actividad pendiente (necesita info): %s — '%s'", category, question)
                    result.append({  # type: ignore[arg-type]
                        "set_pending_activity": {"category": category, "description": description},
                        "clarifying_question": question,
                    })
                    continue
                else:
                    # Generate a clarifying question based on the factor's unit instead of silently dropping
                    _factor_for_q = factors_by_category.get(category)
                    _unit_for_q = _factor_for_q.unit if _factor_for_q else "unidad"
                    _unit_questions: dict[str, str] = {
                        "kg":    f"¿Cuántos gramos de {description} has consumido? (p.ej. 200 para una ración normal)",
                        "litro": f"¿Cuántos litros de {description}? (p.ej. 0.5 para una botella estándar)",
                        "kWh":   f"¿Cuántos kWh de {description}?",
                        "hora":  f"¿Cuántas horas de {description}?",
                        "unidad": f"¿Cuántas unidades de {description}?",
                        "km":    f"¿Cuántos km de {description}?",
                    }
                    question = _unit_questions.get(_unit_for_q, f"¿Cuánto/a {description} has consumido?")
                    log.info("Pregunta aclaratoria generada para actividad sin cantidad: %s", category)
                    result.append({  # type: ignore[arg-type]
                        "set_pending_activity": {"category": category, "description": description},
                        "clarifying_question": question,
                    })
                    continue

            # Validar cantidad
            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    log.warning("Cantidad no positiva ignorada: %s para %s", quantity, category)
                    continue
            except (TypeError, ValueError):
                log.warning("Cantidad inválida ignorada: '%s' para %s", quantity_raw, category)
                continue

            factor = factors_by_category[category]

            # Conversión de unidades
            unit_given = (item.get("unit") or factor.unit or "").lower().strip()
            if factor.unit == "kg" and unit_given in ("g", "gr", "gramos", "gram", "grams"):
                quantity = quantity / 1000
                log.info("Conversión g→kg: %.1f g = %.4f kg para %s", quantity * 1000, quantity, category)
            elif unit_given in ("unidades", "unidad", "piezas", "pieza", "ud", "uds"):
                # Multiplicar el número de piezas por la porción estándar
                _default_q = (user_portions or {}).get(category) or (factor.default_quantity if factor.default_quantity is not None else None)
                if _default_q is not None:
                    original_count = quantity
                    quantity = quantity * _default_q
                    item["description"] = description + f" (×{int(original_count) if original_count == int(original_count) else original_count})"
                    description = item["description"]
                    log.info("Conversión unidades: %.0f × %.4f %s = %.4f %s para %s", original_count, _default_q, factor.unit, quantity, factor.unit, category)
            elif factor.unit == "litro" and unit_given in ("vaso", "vasos"):
                quantity = quantity * 0.25
                log.info("Conversión vaso→litro: %.0f vaso(s) = %.3f L para %s", quantity / 0.25, quantity, category)

            result.append(ExtractedActivity(
                category=category,
                quantity=quantity,
                unit=factor.unit,
                description=description,
                factor=factor,
            ))

        # Separar marcadores especiales de actividades reales
        real_activities = [r for r in result if isinstance(r, ExtractedActivity)]
        set_home_markers = [r for r in result if isinstance(r, dict) and "set_home_city" in r]
        pending_activity_markers = [r for r in result if isinstance(r, dict) and "set_pending_activity" in r]

        # Recopilar preguntas de los marcadores pendientes
        for pa in pending_activity_markers:
            if pa.get("clarifying_question"):
                pending_questions.append(pa["clarifying_question"])

        log.info(
            "Extractor: %d actividades, %d preguntas, %d pending activity — '%s'",
            len(real_activities), len(pending_questions), len(pending_activity_markers), raw_text[:60],
        )

        # Persist unknown items and attach marker so orchestrator can mention them
        unknown_item_markers: list = []
        if unknown_items:
            unknown_names = self._save_unknown_items(unknown_items, raw_text, user_id, db)
            if unknown_names:
                unknown_item_markers = [{"unknown_items": unknown_names}]

        # Construir resultado final: actividades reales + home markers + clear_pending + primer pending activity + pregunta
        clear_pending_markers = [r for r in result if isinstance(r, dict) and r.get("clear_pending")]
        final: list = list(real_activities)

        if set_home_markers:
            final.extend(set_home_markers)

        if clear_pending_markers:
            final.extend(clear_pending_markers)

        # Solo el primer pending_activity (el resto se preguntan en turnos sucesivos)
        if pending_activity_markers:
            first_pending = pending_activity_markers[0]["set_pending_activity"]
            first_pending["question"] = pending_activity_markers[0].get("clarifying_question", "")
            final.append({"set_pending_activity": first_pending})

        if pending_questions and not real_activities and not set_home_markers:
            combined_q = " ".join(pending_questions)
            return [{"clarifying_question": combined_q}] + (
                [{"set_pending_activity": pending_activity_markers[0]["set_pending_activity"]}]
                if pending_activity_markers else []
            )

        if pending_questions:
            final.append({"clarifying_question": " ".join(pending_questions)})

        if unknown_item_markers:
            final.extend(unknown_item_markers)

        return final
