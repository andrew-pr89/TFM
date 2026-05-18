"""
Router de actividades — endpoints MVP.

POST   /activity        → orquesta el agente completo
GET    /history         → historial de actividades del usuario
GET    /summary         → resumen agregado con totales y top categorías
DELETE /history         → borra todo el historial del usuario
DELETE /history/{id}    → borra una actividad concreta
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.memory import MemoryService
from app.agent.orchestrator import carbon_agent
from app.db.database import get_db
from app.models.models import Activity
from app.schemas.schemas import ActivityCreate, ActivityOut, ActivityPatch, ActivityResponse, ImprovementSuggestion, ImprovementsOut, SummaryOut, UserProfile

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


@router.patch("/history/{activity_id}", response_model=ActivityOut)
def patch_activity(activity_id: int, payload: ActivityPatch, user_id: str = "default", db: Session = Depends(get_db)):
    """Edita el texto y/o fecha de una actividad y recalcula sus emisiones."""
    result = carbon_agent.reprocess_activity(
        activity_id=activity_id,
        new_raw_text=payload.raw_text,
        new_created_at=payload.created_at,
        user_id=user_id,
        db=db,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    log.info("Actividad %d actualizada para user=%s", activity_id, user_id)
    return result


@router.get("/summary", response_model=SummaryOut)
def get_summary(user_id: str = "default", period_days: int = 30, annual_goal_kg: int = 6000, db: Session = Depends(get_db)):
    """Resumen agregado de emisiones del usuario en los últimos N días."""
    from collections import defaultdict

    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.created_at >= since)
        .all()
    )

    total_kg = sum(e.amount_kg_co2e for a in activities for e in a.emissions)

    by_category: dict[str, float] = defaultdict(float)
    for activity in activities:
        for emission in activity.emissions:
            by_category[emission.factor.main_category] += emission.amount_kg_co2e

    top = sorted(
        [{"category": k, "total_kg_co2e": round(v, 3)} for k, v in by_category.items()],
        key=lambda x: x["total_kg_co2e"],
        reverse=True,
    )[:5]

    budget_kg = round(period_days * (annual_goal_kg / 365), 2)

    return SummaryOut(
        user_id=user_id,
        total_activities=len(activities),
        total_kg_co2e=round(total_kg, 3),
        top_categories=top,
        period_days=period_days,
        budget_kg_co2e=budget_kg,
    )


@router.get("/profile", response_model=UserProfile)
def get_profile(user_id: str = "default", db: Session = Depends(get_db)):
    """Devuelve el perfil del usuario guardado en memoria."""
    memory = MemoryService()
    data = memory.get_memory(user_id=user_id, db=db)
    return UserProfile(
        home_city=data.get("home_city"),
        work_place=data.get("work_place"),
        display_name=data.get("display_name"),
    )


@router.patch("/profile", response_model=UserProfile)
def update_profile(payload: UserProfile, user_id: str = "default", db: Session = Depends(get_db)):
    """Guarda o actualiza el perfil del usuario."""
    memory = MemoryService()
    updates: dict[str, str] = {}
    if payload.home_city is not None:
        updates["home_city"] = payload.home_city
    if payload.work_place is not None:
        updates["work_place"] = payload.work_place
    if payload.display_name is not None:
        updates["display_name"] = payload.display_name
    if updates:
        memory.update_memory(user_id=user_id, updates=updates, db=db)
        db.commit()
    return get_profile(user_id=user_id, db=db)


@router.get("/improvements", response_model=ImprovementsOut)
def get_improvements(user_id: str = "default", period_days: int = 30, annual_goal_kg: int = 6000, db: Session = Depends(get_db)):
    """Genera sugerencias de mejora personalizadas basadas en el consumo real del usuario."""
    from collections import defaultdict
    from app.agent.llm_service import LLMService

    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.created_at >= since)
        .all()
    )

    if not activities:
        return ImprovementsOut(suggestions=[], total_kg=0.0, budget_kg=round(period_days * (2000 / 365), 2), period_days=period_days)

    total_kg = sum(e.amount_kg_co2e for a in activities for e in a.emissions)
    budget_kg = round(period_days * (annual_goal_kg / 365), 2)

    by_category: dict[str, float] = defaultdict(float)
    by_factor: dict[str, float] = defaultdict(float)
    for activity in activities:
        for emission in activity.emissions:
            by_category[emission.factor.main_category] += emission.amount_kg_co2e
            by_factor[emission.factor.display_name] += emission.amount_kg_co2e

    sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    cats_payload = [
        {"category": cat, "kg": round(kg, 3), "pct": round(kg / total_kg * 100, 1)}
        for cat, kg in sorted_cats
    ]

    sorted_factors = sorted(by_factor.items(), key=lambda x: x[1], reverse=True)
    factors_payload = [
        {"name": name, "kg": round(kg, 3)}
        for name, kg in sorted_factors
    ]

    llm = LLMService()
    raw_suggestions = llm.generate_improvements(
        total_kg=total_kg,
        budget_kg=budget_kg,
        by_category=cats_payload,
        by_factor=factors_payload,
        period_days=period_days,
    )

    suggestions = []
    for s in raw_suggestions:
        cat_name = s.get("category", "")
        cat_kg = by_category.get(cat_name, 0.0)
        suggestions.append(ImprovementSuggestion(
            category=cat_name,
            current_kg=round(cat_kg, 3),
            pct_of_total=round(cat_kg / total_kg * 100, 1) if total_kg > 0 else 0.0,
            action=s.get("action", ""),
            tip=s.get("tip", ""),
            potential_saving_pct=int(s.get("potential_saving_pct", 10)),
        ))

    return ImprovementsOut(
        suggestions=suggestions,
        total_kg=round(total_kg, 3),
        budget_kg=budget_kg,
        period_days=period_days,
    )