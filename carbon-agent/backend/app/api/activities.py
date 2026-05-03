"""
Router de actividades — endpoints MVP.

POST /activity   → orquesta el agente completo (Extractor → Calculadora → Recomendador)
GET  /history    → historial de actividades del usuario
GET  /summary    → resumen agregado con totales y top categorías
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.orchestrator import carbon_agent
from app.db.database import get_db
from app.models.models import Activity
from app.schemas.schemas import ActivityCreate, ActivityOut, ActivityResponse, SummaryOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["activities"])


@router.post("/activity", response_model=ActivityResponse, status_code=201)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    """
    Registra una actividad en lenguaje natural y calcula su huella de carbono.

    Flujo:
      1. Extractor LLM → identifica actividades en el texto
      2. Calculadora CO₂ → cálculo determinista (quantity × factor)
      3. Persiste Activity + Emissions en BD
      4. Recomendador LLM → recomendación personalizada
      5. Devuelve total kg CO₂e + recomendación
    """
    try:
        return carbon_agent.process_activity(
            raw_text=payload.raw_text,
            user_id=payload.user_id,
            db=db,
        )
    except Exception as exc:
        log.error("Error procesando actividad: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error del agente: {str(exc)}")


@router.get("/history", response_model=list[ActivityOut])
def get_history(user_id: str = "default", limit: int = 50, db: Session = Depends(get_db)):
    """Devuelve el historial de actividades de un usuario, más reciente primero."""
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )
    return activities


@router.get("/summary", response_model=SummaryOut)
def get_summary(user_id: str = "default", period_days: int = 30, db: Session = Depends(get_db)):
    """Resumen agregado de emisiones del usuario en los últimos N días."""
    from collections import defaultdict

    since = datetime.utcnow() - timedelta(days=period_days)

    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.created_at >= since)
        .all()
    )

    total_kg = sum(
        e.amount_kg_co2e
        for a in activities
        for e in a.emissions
    )

    by_category: dict[str, float] = defaultdict(float)
    for activity in activities:
        for emission in activity.emissions:
            by_category[emission.factor.category] += emission.amount_kg_co2e

    top = sorted(
        [{"category": k, "total_kg_co2e": round(v, 3)} for k, v in by_category.items()],
        key=lambda x: x["total_kg_co2e"],
        reverse=True,
    )[:5]

    return SummaryOut(
        user_id=user_id,
        total_activities=len(activities),
        total_kg_co2e=round(total_kg, 3),
        top_categories=top,
        period_days=period_days,
    )