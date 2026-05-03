"""
Router de actividades — endpoints MVP.

POST   /activity        → orquesta el agente completo
GET    /history         → historial de actividades del usuario
GET    /summary         → resumen agregado con totales y top categorías
DELETE /history         → borra todo el historial del usuario
DELETE /history/{id}    → borra una actividad concreta
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
    return (
        db.query(Activity)
        .filter(Activity.user_id == user_id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )


@router.delete("/history", status_code=204)
def delete_history(user_id: str = "default", db: Session = Depends(get_db)):
    """Borra todo el historial del usuario (cascade elimina las emisiones asociadas)."""
    deleted = (
        db.query(Activity)
        .filter(Activity.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    log.info("Historial borrado: user=%s, %d actividades eliminadas", user_id, deleted)


@router.delete("/history/{activity_id}", status_code=204)
def delete_activity(activity_id: int, user_id: str = "default", db: Session = Depends(get_db)):
    """Borra una actividad concreta y sus emisiones."""
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.user_id == user_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    db.delete(activity)
    db.commit()
    log.info("Actividad %d eliminada para user=%s", activity_id, user_id)


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

    total_kg = sum(e.amount_kg_co2e for a in activities for e in a.emissions)

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