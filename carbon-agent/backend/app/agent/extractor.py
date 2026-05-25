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
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent.distance_service import get_distance_km
from app.agent.llm_service import LLMService
from app.models.models import EmissionFactor

log = logging.getLogger(__name__)


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

    def extract(
        self,
        raw_text: str,
        db: Session,
        home_city: str | None = None,
        work_place: str | None = None,
        pending_activity: dict | None = None,
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
        factors_by_category: dict[str, EmissionFactor] = {
            f.category: f
            for f in db.query(EmissionFactor).all()
        }

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

        if not raw_activities:
            log.info("El LLM no identificó actividades con impacto CO₂ en: '%s'", raw_text[:80])
            return []

        # 3 & 4. Validación y resolución — procesar TODAS las actividades
        result: list[ExtractedActivity] = []
        pending_questions: list[str] = []

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
            quantity_raw = item.get("quantity")
            description = item.get("description", category)

            # Validar categoría
            if category not in factors_by_category:
                log.warning("Categoría desconocida ignorada: '%s'", category)
                continue

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
                    log.warning("Actividad sin cantidad ni ciudades ignorada: %s", category)
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
