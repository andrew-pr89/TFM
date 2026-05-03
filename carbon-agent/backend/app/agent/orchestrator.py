"""
Orquestador del agente — coordina todos los componentes.

Flujo completo de POST /activity:
  1. Extractor LLM    → identifica actividades en texto natural
  2. Calculadora CO₂  → cálculo determinista (sin LLM)
  3. Persistencia     → guarda Activity + Emissions en BD
  4. Memoria          → actualiza hábitos del usuario
  5. Recomendador LLM → genera recomendación personalizada
  6. Devuelve         → total kg CO₂e + recomendación

Diseñado para evolucionar a multi-agente: cada componente es independiente
y puede convertirse en un agente especializado sin cambiar la interfaz.
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
    """
    Agente único del MVP.

    Orquesta Extractor → Calculadora → Memoria → Recomendador
    en una sola llamada síncrona.
    """

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
        """
        Procesa una actividad de principio a fin.

        Parámetros:
            raw_text: texto libre introducido por el usuario
            user_id:  identificador del usuario
            db:       sesión SQLAlchemy (inyectada por FastAPI)

        Devuelve ActivityResponse con total CO₂ y recomendación.
        """
        # ── 1. Persistir la actividad (texto crudo) ──────────────────────────
        activity = Activity(user_id=user_id, raw_text=raw_text)
        db.add(activity)
        db.flush()  # obtiene el id sin hacer commit todavía

        # ── 2. Extracción (LLM) ──────────────────────────────────────────────
        extracted = self.extractor.extract(raw_text=raw_text, db=db)

        if not extracted:
            db.commit()
            log.info("No se encontraron actividades CO₂ en el texto.")
            return ActivityResponse(
                activity=ActivityOut.model_validate(activity),
                total_kg_co2e=0.0,
                recommendation=(
                    "No he podido identificar actividades con huella de carbono en tu mensaje. "
                    "Prueba con algo como: 'he conducido 20 km' o 'comí carne de vacuno'."
                ),
            )

        # ── 3. Cálculo CO₂ (determinista, sin LLM) ──────────────────────────
        results = self.calculator.calculate(
            activity=activity,
            extracted_activities=extracted,
            db=db,
        )
        total = self.calculator.total(results)

        # ── 4. Commit de actividad + emisiones ───────────────────────────────
        db.commit()
        db.refresh(activity)

        # ── 5. Actualizar memoria del usuario ────────────────────────────────
        for r in results:
            self.memory.infer_habits(
                user_id=user_id,
                category=r.extracted.category,
                db=db,
            )
        db.commit()

        # ── 6. Recomendación personalizada (LLM) ─────────────────────────────
        user_memory = self.memory.get_memory(user_id=user_id, db=db)

        activities_summary = [
            {
                "description": r.extracted.description,
                "amount_kg_co2e": r.amount_kg_co2e,
            }
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


# Singleton — una sola instancia compartida por todos los requests
carbon_agent = CarbonAgent()
