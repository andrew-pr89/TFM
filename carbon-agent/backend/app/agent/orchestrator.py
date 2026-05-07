"""
Orquestador del agente — coordina todos los componentes.

Flujo completo de POST /activity:
  1. Extractor LLM    → identifica actividades en texto natural
  2. Si no hay actividades → devuelve mensaje, NO persiste nada
  3. Calculadora CO₂  → cálculo determinista (sin LLM)
  4. Persistencia     → guarda Activity + Emissions en BD
  5. Memoria          → actualiza hábitos del usuario
  6. Recomendador LLM → genera recomendación personalizada
  7. Devuelve         → total kg CO₂e + recomendación
"""

import logging

from sqlalchemy.orm import Session

from app.agent.calculator import CO2Calculator
from app.agent.extractor import Extractor
from app.agent.llm_service import LLMService
from app.agent.memory import MemoryService
from app.models.models import Activity
from app.schemas.schemas import ActivityOut, ActivityResponse

log = logging.getLogger(__name__)


class CarbonAgent:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.extractor = Extractor(llm=self.llm)
        self.calculator = CO2Calculator()
        self.memory = MemoryService()

    def process_activity(
        self,
        raw_text: str,
        user_id: str,
        db: Session,
    ) -> ActivityResponse:
        # ── 1. Extracción (LLM) — ANTES de persistir ────────────────────────
        # Necesitamos los factores de BD para el extractor, pero aún no
        # creamos la Activity. Si no hay nada que guardar, no tocamos la BD.
        extracted = self.extractor.extract(raw_text=raw_text, db=db)

        # Verificar si hay una pregunta aclaratoria
        if extracted and len(extracted) == 1 and isinstance(extracted[0], dict):
            if "clarifying_question" in extracted[0]:
                log.info("Pregunta aclaratoria: %s", extracted[0]["clarifying_question"])
                return ActivityResponse(
                    activity=ActivityOut(
                        id=-1,
                        user_id=user_id,
                        raw_text=raw_text,
                        created_at=__import__("datetime").datetime.utcnow(),
                        emissions=[],
                    ),
                    total_kg_co2e=0.0,
                    recommendation=extracted[0]["clarifying_question"],
                    is_question=True,
                )

        if not extracted:
            log.info("Nada que guardar — el LLM no identificó actividades CO₂.")
            # Devolvemos una ActivityOut vacía sin id real (no persistida)
            return ActivityResponse(
                activity=ActivityOut(
                    id=-1,
                    user_id=user_id,
                    raw_text=raw_text,
                    created_at=__import__("datetime").datetime.utcnow(),
                    emissions=[],
                ),
                total_kg_co2e=0.0,
                recommendation=(
                    "No he podido identificar actividades con huella de carbono en tu mensaje. "
                    "Prueba con algo como: 'he conducido 20 km', 'comí un filete de ternera' "
                    "o 'vuelo Madrid-Londres'."
                ),
            )

        # ── 2. Persistir Activity ────────────────────────────────────────────
        activity = Activity(user_id=user_id, raw_text=raw_text)
        db.add(activity)
        db.flush()  # obtiene id sin commit

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


carbon_agent = CarbonAgent()