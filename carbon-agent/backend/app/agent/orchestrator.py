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

        # ── 1. Cargar contexto de memoria antes de extraer ───────────────────
        home_city = self.memory.get_home_city(user_id=user_id, db=db)

        # ── 2. Extracción (LLM) — ANTES de persistir ────────────────────────
        extracted = self.extractor.extract(raw_text=raw_text, db=db, home_city=home_city)

        # ── Separar marcadores especiales de actividades reales ──────────────
        new_home_city: str | None = None
        pending_question: str | None = None

        # Los marcadores siempre van al final de la lista
        filtered = []
        for item in extracted:
            if isinstance(item, dict) and "set_home_city" in item:
                new_home_city = item["set_home_city"]
            elif isinstance(item, dict) and "clarifying_question" in item:
                pending_question = item["clarifying_question"]
            else:
                filtered.append(item)
        extracted = filtered

        # Guardar home_city si el LLM la detectó
        if new_home_city:
            self.memory.set_home_city(user_id=user_id, city=new_home_city, db=db)
            db.commit()
            log.info("home_city guardada para user=%s: %s", user_id, new_home_city)

        # ── Caso: solo pregunta, sin actividades ─────────────────────────────
        if pending_question and not extracted:
            log.info("Pregunta aclaratoria para user=%s: %s", user_id, pending_question)
            response = _empty(user_id, raw_text)
            response.recommendation = pending_question
            response.is_question = True
            return response

        # ── Caso: solo se declaró ciudad de origen, sin actividades CO₂ ───────
        if not extracted and not pending_question and new_home_city:
            response = _empty(user_id, raw_text)
            response.recommendation = (
                f"¡Perfecto! He guardado {new_home_city} como tu ciudad de origen. "
                "La usaré automáticamente para calcular distancias cuando viajes."
            )
            return response

        # ── Caso: nada identificado ──────────────────────────────────────────
        if not extracted and not pending_question:
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

        # Si había actividades incompletas, añadir la pregunta a la recomendación
        if pending_question:
            recommendation = f"{recommendation}\n\nAdemás, necesito más información: {pending_question}"

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

        home_city = self.memory.get_home_city(user_id=user_id, db=db)
        extracted = self.extractor.extract(new_raw_text, db, home_city=home_city)
        # Filtrar marcadores especiales antes de calcular
        extracted = [
            e for e in extracted
            if not (isinstance(e, dict) and ("clarifying_question" in e or "set_home_city" in e))
        ]
        if extracted:
            self.calculator.calculate(activity=activity, extracted_activities=extracted, db=db)

        db.commit()
        db.refresh(activity)
        return ActivityOut.model_validate(activity)


carbon_agent = CarbonAgent()