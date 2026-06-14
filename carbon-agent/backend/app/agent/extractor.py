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
# Used when the user mentions an item without specifying a quantity.
DEFAULT_PORTIONS: dict[str, float] = {
    # Carnes (kg)
    "carne_vacuno":    0.30,   # 300g — filete/chuletón estándar
    "carne_cerdo":     0.20,   # 200g — chuleta de cerdo
    "carne_pollo":     0.15,   # 150g — pechuga de pollo
    "carne_procesada": 0.05,   # 50g  — ración de embutido
    "pescado":         0.15,   # 150g — filete de pescado
    "marisco":         0.15,   # 150g
    "queso":           0.05,   # 50g  — ración de queso
    "tofu_soja":       0.15,   # 150g
    # Cereales, legumbres, vegetales (kg)
    "cereales":        0.10,   # 100g — ración pasta/pan (peso seco)
    "arroz":           0.10,   # 100g — ración arroz (peso seco)
    "legumbres":       0.08,   # 80g  — ración legumbres (peso seco)
    "patata":          0.20,   # 200g
    "fruta":           0.15,   # 150g — 1 pieza mediana
    "verduras":        0.15,   # 150g
    # Lácteos y bebidas (litro)
    "lacteos_leche":   0.20,   # 200ml — 1 vaso
    "alcohol_cerveza": 0.33,   # 330ml — 1 botella/lata
    "alcohol_vino":    0.15,   # 150ml — 1 copa
    "agua_embotellada":0.50,   # 500ml — 1 botella
    "zumo":            0.20,   # 200ml — 1 vaso
    "aceite_oliva":    0.02,   # 20ml  — 1 cucharada
    # Café (kg — grano molido por taza)
    "cafe":            0.012,  # ~12g por taza
    "chocolate":       0.05,   # 50g — 1 onza/tableta pequeña
    # Unidades
    "huevos":          2.0,    # 2 huevos
    "comida_rapida":   1.0,    # 1 unidad (hamburguesa/pizza)
    "refresco_lata":   1.0,    # 1 lata
    "ropa_nueva":      1.0,
    "zapatillas":      1.0,
    "libro_nuevo":     1.0,
    "streaming":       1.0,
    "gimnasio":        1.0,
    "hotel":           1.0,
    "crucero":         1.0,
    "lavadora":        1.0,
    "secadora":        1.0,
    "lavavajillas":    1.0,
    # Energía (kWh o hora)
    "electricidad_es": 10.0,   # 10 kWh — consumo diario medio hogar
    "gas_natural":     5.0,    # 5 kWh
    "aire_acondicionado": 2.0, # 2 horas
    "television":      2.0,    # 2 horas
}


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
            if norm_term in _norm(f.display_name) or _norm(f.display_name) in norm_term
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
        pending_activity: dict | None = None,
        user_portions: dict[str, float] | None = None,
        user_id: str = "default",
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
        )

        log.info("LLM devolvió %d actividades para: '%s'", len(raw_activities), raw_text[:60])
        if raw_activities:
            log.info("Actividades LLM: %s", [
                {"cat": a.get("category"), "qty": a.get("quantity")}
                for a in raw_activities if isinstance(a, dict)
            ])

        if not raw_activities:
            log.info("El LLM no identificó actividades con impacto CO₂ en: '%s'", raw_text[:80])
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
                    else:
                        truly_unknown.append({"category": "unknown", "description": term, "guessed_type": c.get("guessed_type")})

                if fuzzy_pending:
                    unknown_names = self._save_unknown_items(truly_unknown, raw_text, user_id, db) if truly_unknown else []
                    # Return the first pending question (subsequent ones handled in next turns)
                    first = fuzzy_pending[0]
                    pending_data = first["set_pending_activity"]
                    pending_data["question"] = first["clarifying_question"]
                    result_list: list = [{"set_pending_activity": pending_data}, {"clarifying_question": first["clarifying_question"]}]
                    if unknown_names:
                        result_list.append({"unknown_items": unknown_names})
                    return result_list  # type: ignore[return-value]

                items_as_unknown = truly_unknown
                names = self._save_unknown_items(items_as_unknown, raw_text, user_id, db)
                if names:
                    return [{"unknown_items": names}]  # type: ignore[list-item]
            return []

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
            if "set_home_city" in item or ("clarifying_question" in item and not item.get("category")):
                result.append(item)  # type: ignore[arg-type]
                continue

            category = item.get("category", "").strip()

            # Item marcado como desconocido por el LLM → registrar para revisión
            if category == "unknown":
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
                    # Priority: user override > factor.default_quantity (admin) > DEFAULT_PORTIONS (hardcoded) > 1 for unidad
                    _default_q = (user_portions or {}).get(category)
                    if _default_q is None and _factor_unit and _factor_unit.default_quantity is not None:
                        _default_q = _factor_unit.default_quantity
                    if _default_q is None:
                        _default_q = DEFAULT_PORTIONS.get(category)
                    if _default_q is None and _factor_unit and _factor_unit.unit == "unidad":
                        _default_q = 1.0
                    if _default_q is not None:
                        quantity_raw = _default_q
                        item["description"] = description + " (ración estándar)"
                        description = item["description"]
                        log.info("Usando porción estándar para %s: %s %s", category, _default_q, _factor_unit.unit if _factor_unit else "")

            if quantity_raw is None:
                # Intentar calcular distancia desde ciudades/lugares
                origin = (item.get("origin") or "").strip()
                destination = (item.get("destination") or "").strip()

                # Si hay origen y destino explícitos (dos lugares)
                if origin and destination:
                    if origin.lower() in _GENERIC_PLACES or destination.lower() in _GENERIC_PLACES:
                        log.info("Origen/destino genérico ('%s'/'%s') — actividad pendiente", origin, destination)
                        question = item.get("clarifying_question") or (
                            f"¿Desde qué lugar exacto y hasta dónde en {description}? "
                            "(p.ej: 'desde el aeropuerto de Madrid hasta el hotel Meliá Castilla')"
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
                        item["description"] = description + f" ({origin} → {destination}, {probe:.0f} km)"
                        description = item["description"]
                    else:
                        log.info("Calculando distancia %s → %s", origin, destination)
                        quantity_raw = get_distance_km(origin, destination)
                        if quantity_raw is None or (
                            category in _URBAN_TRANSPORT and quantity_raw > _max_km(category)
                        ):
                            if quantity_raw and quantity_raw > _max_km(category):
                                log.warning("Distancia %s → %s = %.0f km parece incorrecta para %s", origin, destination, quantity_raw, category)
                                question = f"No pude calcular bien la distancia para {description}. ¿Cuántos km son aproximadamente?"
                            else:
                                log.warning("No se pudo calcular distancia %s → %s", origin, destination)
                                question = f"No pude calcular la distancia entre {origin} y {destination}. ¿Cuántos km son aproximadamente?"
                            result.append({  # type: ignore[arg-type]
                                "set_pending_activity": {"category": category, "description": description},
                                "clarifying_question": question,
                            })
                            continue
                        item["description"] = description + f" ({origin} → {destination}, {quantity_raw:.0f} km)"
                        description = item["description"]

                # Solo hay destino — usar home_city como origen si está disponible
                elif destination and not origin:
                    if destination.lower() in _GENERIC_PLACES:
                        question = item.get("clarifying_question") or (
                            f"¿Desde qué lugar exacto y hasta dónde en {description}? "
                            "(p.ej: 'desde el aeropuerto de Madrid hasta el hotel Meliá Castilla')"
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
                            if quantity_raw and quantity_raw > _max_km(category):
                                log.warning("Distancia %s → %s = %.0f km parece incorrecta para %s", home_city, destination, quantity_raw, category)
                                question = f"No pude calcular bien la distancia para {description}. ¿Cuántos km son aproximadamente?"
                            else:
                                log.warning("No se pudo calcular distancia %s → %s", home_city, destination)
                                question = f"No pude calcular la distancia entre {home_city} y {destination}. ¿Cuántos km son aproximadamente?"
                            result.append({  # type: ignore[arg-type]
                                "set_pending_activity": {"category": category, "description": description, "destination": destination},
                                "clarifying_question": question,
                            })
                            continue
                        item["description"] = description + f" ({home_city} → {destination}, {quantity_raw:.0f} km)"
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
                _default_q = (user_portions or {}).get(category) or DEFAULT_PORTIONS.get(category)
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
        if unknown_items:
            unknown_names = self._save_unknown_items(unknown_items, raw_text, user_id, db)
            if unknown_names:
                result.append({"unknown_items": unknown_names})  # type: ignore[arg-type]

        # Construir resultado final: actividades reales + home markers + primer pending activity + pregunta
        final: list = list(real_activities)

        if set_home_markers:
            final.extend(set_home_markers)

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

        return final
