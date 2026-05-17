"""
Calculadora CO₂ — cálculo 100% determinista.

Fórmula única:
    emisiones (kg CO₂e) = cantidad × factor_kg_co2e

El LLM NO interviene en ningún punto de este módulo.
Recibe ExtractedActivity (con el factor ya resuelto) y devuelve Emission ORM.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent.extractor import ExtractedActivity
from app.models.models import Activity, Emission

log = logging.getLogger(__name__)


@dataclass
class CalculationResult:
    """Resultado del cálculo para una actividad individual."""
    extracted: ExtractedActivity
    emission: Emission          # objeto ORM listo para persistir
    amount_kg_co2e: float


class CO2Calculator:
    """
    Calcula las emisiones de CO₂ de forma determinista.

    No hace ninguna llamada externa. Solo aritmética con los factores de la BD.
    """

    def calculate(
        self,
        activity: Activity,
        extracted_activities: list[ExtractedActivity],
        db: Session,
    ) -> list[CalculationResult]:
        """
        Calcula las emisiones para todas las actividades extraídas.

        Para cada ExtractedActivity:
            amount = quantity × factor.factor_kg_co2e

        Persiste los objetos Emission en la sesión (sin commit — lo hace el orquestador).
        """
        results: list[CalculationResult] = []

        for extracted in extracted_activities:
            amount = round(extracted.quantity * extracted.factor.factor_kg_co2e, 6)

            emission = Emission(
                activity_id=activity.id,
                factor_id=extracted.factor.id,
                quantity=extracted.quantity,
                amount_kg_co2e=amount,
                description=extracted.description,
            )
            db.add(emission)

            log.info(
                "CO₂: %s × %.6f = %.6f kg CO₂e  [%s]",
                extracted.quantity,
                extracted.factor.factor_kg_co2e,
                amount,
                extracted.category,
            )

            results.append(CalculationResult(
                extracted=extracted,
                emission=emission,
                amount_kg_co2e=amount,
            ))

        return results

    @staticmethod
    def total(results: list[CalculationResult]) -> float:
        """Suma total de emisiones en kg CO₂e, redondeada a 3 decimales."""
        return round(sum(r.amount_kg_co2e for r in results), 3)
