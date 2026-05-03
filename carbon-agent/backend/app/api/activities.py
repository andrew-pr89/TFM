"""
Router de actividades — endpoints MVP.

POST /activity   → registra texto, extrae actividades, calcula CO₂, devuelve total
GET  /history    → historial de actividades del usuario
GET  /summary    → resumen agregado con totales y top categorías

La lógica de negocio (extractor, calculadora, recomendador) se implementará
en la Fase 2. Aquí los endpoints devuelven stubs para que el frontend
pueda integrarse desde ya.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Activity, Emission
from app.schemas.schemas import ActivityCreate, ActivityOut, ActivityResponse, SummaryOut

router = APIRouter(prefix="/api", tags=["activities"])


@router.post("/activity", response_model=ActivityResponse, status_code=201)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    """
    Registra una actividad en lenguaje natural.

    Flujo completo (Fase 2):
      1. Extractor LLM → JSON estructurado
      2. Calculadora CO₂ → cálculo determinista
      3. Guarda Activity + Emissions en BD
      4. Recomendador LLM → texto personalizado
      5. Devuelve total + recomendación

    Fase 1: persiste el texto y devuelve stub hasta que el agente esté listo.
    """
    activity = Activity(user_id=payload.user_id, raw_text=payload.raw_text)
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return ActivityResponse(
        activity=ActivityOut.model_validate(activity),
        total_kg_co2e=0.0,
        recommendation="[Fase 2] El agente calculará las emisiones y generará una recomendación.",
    )


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
    from datetime import datetime, timedelta
    from sqlalchemy import func

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

    # Top categorías agregadas
    from collections import defaultdict
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
