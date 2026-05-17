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

    def extract(self, raw_text: str, db: Session, home_city: str | None = None) -> list[ExtractedActivity]:
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
                # Intentar calcular distancia desde ciudades
                origin = (item.get("origin") or "").strip()
                destination = (item.get("destination") or "").strip()

                # Si hay origen explícito entre dos ciudades reales
                if origin and destination:
                    if origin.lower() in _GENERIC_PLACES or destination.lower() in _GENERIC_PLACES:
                        log.info("Origen/destino genérico ('%s'/'%s') — añadiendo pregunta", origin, destination)
                        pending_questions.append(
                            item.get("clarifying_question") or "¿Cuántos km has recorrido aproximadamente?"
                        )
                        continue
                    log.info("Calculando distancia %s → %s", origin, destination)
                    quantity_raw = get_distance_km(origin, destination)
                    if quantity_raw is None:
                        log.warning("No se pudo calcular distancia %s → %s", origin, destination)
                        pending_questions.append(
                            f"No pude calcular la distancia entre {origin} y {destination}. ¿Cuántos km son aproximadamente?"
                        )
                        continue
                    item["description"] = description + f" ({origin} → {destination}, {quantity_raw:.0f} km)"
                    description = item["description"]

                # Solo hay destino (origin=null) — usar home_city si está disponible
                elif destination and not origin:
                    if destination.lower() in _GENERIC_PLACES:
                        pending_questions.append(
                            item.get("clarifying_question") or "¿Cuántos km has recorrido aproximadamente?"
                        )
                        continue
                    if home_city:
                        log.info("Usando home_city '%s' como origen para → %s", home_city, destination)
                        quantity_raw = get_distance_km(home_city, destination)
                        if quantity_raw is None:
                            log.warning("No se pudo calcular distancia %s → %s", home_city, destination)
                            pending_questions.append(
                                f"No pude calcular la distancia entre {home_city} y {destination}. ¿Cuántos km son aproximadamente?"
                            )
                            continue
                        item["description"] = description + f" ({home_city} → {destination}, {quantity_raw:.0f} km)"
                        description = item["description"]
                    else:
                        # Sin home_city conocida — preguntar la ciudad de origen
                        pending_questions.append(
                            item.get("clarifying_question")
                            or "¿Desde qué ciudad saliste? La recordaré para la próxima vez."
                        )
                        continue

                elif item.get("clarifying_question"):
                    pending_questions.append(item["clarifying_question"])
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
            unit_given = item.get("unit", factor.unit).lower().strip()
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

        log.info(
            "Extractor: %d actividades válidas, %d preguntas pendientes — '%s'",
            len(real_activities), len(pending_questions), raw_text[:60],
        )

        # Construir resultado final: actividades reales + marcadores + preguntas al final
        final: list = list(real_activities)

        if set_home_markers:
            final.extend(set_home_markers)

        if pending_questions and not real_activities:
            return [{"clarifying_question": " ".join(pending_questions)}] + set_home_markers

        if pending_questions:
            final.append({"clarifying_question": " ".join(pending_questions)})

        return final
