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

    def extract(self, raw_text: str, db: Session) -> list[ExtractedActivity]:
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

        # Verificar si hay una pregunta aclaratoria
        if len(raw_activities) == 1 and "clarifying_question" in raw_activities[0]:
            # Retornar la pregunta como un marcador especial
            log.info("Pregunta aclaratoria del LLM: %s", raw_activities[0]["clarifying_question"])
            return raw_activities  # Retorna [{"clarifying_question": "..."}]

        # 3 & 4. Validación y resolución
        result: list[ExtractedActivity] = []

        for item in raw_activities:
            category = item.get("category", "").strip()
            quantity_raw = item.get("quantity")
            description = item.get("description", category)

            # Validar categoría
            if category not in factors_by_category:
                log.warning("Categoría desconocida ignorada: '%s'", category)
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

            # Conversión de unidades: si el LLM devuelve gramos pero el factor es en kg
            unit_given = item.get("unit", factor.unit).lower().strip()
            if factor.unit == "kg" and unit_given in ("g", "gr", "gramos", "gram", "grams"):
                quantity = quantity / 1000
                log.info("Conversión g→kg: %.1f g = %.4f kg para %s", quantity * 1000, quantity, category)

            result.append(ExtractedActivity(
                category=category,
                quantity=quantity,
                unit=factor.unit,
                description=description,
                factor=factor,
            ))

        log.info("Extractor: %d actividades válidas extraídas de '%s'", len(result), raw_text[:60])
        return result
