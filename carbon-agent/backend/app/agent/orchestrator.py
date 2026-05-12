"""
Orquestador del agente — coordina todos los componentes.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.calculator import CO2Calculator
from app.agent.extractor import Extractor, ExtractedActivity
from app.agent.llm_service import LLMService
from app.agent.memory import MemoryService
from app.models.models import Activity
from app.schemas.schemas import ActivityOut, ActivityResponse

log = logging.getLogger(__name__)


def _empty(user_id: str, raw_text: str) -> ActivityResponse:
    return ActivityResponse(
        activity=ActivityOut(
            id=-1,
            user_id=user_id,
            raw_text=raw_text,
            created_at=datetime.utcnow(),
            emissions=[],
        ),
        total_kg_co2e=0.0,
        recommendation="",
    )


class CarbonAgent:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.extractor = Extractor(llm=self.llm)
        self.calculator = CO2Calculator()
        self.memory = MemoryService()

    def process_activity(self, raw_text: str, user_id: str, db: Session) -> ActivityResponse:

        # ── 1. Extracción (LLM) — ANTES de persistir ────────────────────────
        extracted = self.extractor.extract(raw_text=raw_text, db=db)

        # ── Caso: pregunta aclaratoria ───────────────────────────────────────
        # El extractor devuelve dicts cuando hay clarifying_question,
        # y ExtractedActivity cuando hay actividades válidas.
        if extracted and isinstance(extracted[0], dict) and "clarifying_question" in extracted[0]:
            question = extracted[0]["clarifying_question"]
            log.info("Pregunta aclaratoria para user=%s: %s", user_id, question)
            response = _empty(user_id, raw_text)
            response.recommendation = question
            response.is_question = True
            return response

        # ── Caso: nada identificado ──────────────────────────────────────────
        if not extracted:
            log.info("Nada que guardar — el LLM no identificó actividades CO₂.")
            response = _empty(user_id, raw_text)
            response.recommendation = (
                "No he podido identificar actividades con huella de carbono en tu mensaje. "
                "Prueba con algo como: 'he conducido 20 km', 'comí 200g de ternera' "
                "o 'vuelo Madrid-Londres de 600 km'."
            )
            return response

        # ── 2. Persistir Activity ────────────────────────────────────────────
        activity = Activity(user_id=user_id, raw_text=raw_text)
        db.add(activity)
        db.flush()

        # ── 3. Cálculo CO₂ (determinista, sin LLM) ──────────────────────────
        results = self.calculator.calculate(
            activity=activity,
            extracted_activities=extracted,
            db=db,
        )
        total = self.calculator.total(results)

        # ── 4. Commit ────────────────────────────────────────────────────────
        db.commit()
        db.refresh(activity)

        # ── 5. Actualizar memoria ────────────────────────────────────────────
        for r in results:
            self.memory.infer_habits(user_id=user_id, category=r.extracted.category, db=db)
        db.commit()

        # ── 6. Recomendación (LLM) ───────────────────────────────────────────
        user_memory = self.memory.get_memory(user_id=user_id, db=db)
        activities_summary = [
            {"description": r.extracted.description, "amount_kg_co2e": r.amount_kg_co2e}
            for r in results
        ]

        try:
            recommendation = self.llm.generate_recommendation(
                total_kg_co2e=total,
                activities_summary=activities_summary,
                user_memory=user_memory,
            )
        except Exception as exc:
            log.error("Error generando recomendación: %s", exc)
            recommendation = f"Has generado {total:.3f} kg CO₂e. ¡Intenta reducir tu huella mañana!"

        log.info("Actividad procesada: user=%s total=%.3f kg CO₂e", user_id, total)

        return ActivityResponse(
            activity=ActivityOut.model_validate(activity),
            total_kg_co2e=total,
            recommendation=recommendation,
        )


    def reprocess_activity(
        self,
        activity_id: int,
        new_raw_text: str,
        new_created_at,
        user_id: str,
        db: Session,
    ) -> "ActivityOut | None":
        activity = (
            db.query(Activity)
            .filter(Activity.id == activity_id, Activity.user_id == user_id)
            .first()
        )
        if not activity:
            return None

        activity.raw_text = new_raw_text
        if new_created_at:
            activity.created_at = new_created_at

        activity.emissions.clear()
        db.flush()

        extracted = self.extractor.extract(new_raw_text, db)
        if extracted and not (isinstance(extracted[0], dict) and "clarifying_question" in extracted[0]):
            self.calculator.calculate(activity=activity, extracted_activities=extracted, db=db)

        db.commit()
        db.refresh(activity)
        return ActivityOut.model_validate(activity)


carbon_agent = CarbonAgent()