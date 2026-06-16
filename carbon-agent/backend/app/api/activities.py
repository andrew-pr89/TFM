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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.extractor import DEFAULT_PORTIONS
from app.agent.memory import MemoryService
from app.agent.orchestrator import carbon_agent
from app.core.auth import get_admin_user, get_current_user
from app.db.database import get_db
from app.db.seed_data import EMISSION_FACTORS
from app.models.models import Activity, EmissionFactor
from app.schemas.schemas import ActivityCreate, ActivityOut, ActivityPatch, ActivityResponse, EmissionFactorCreate, EmissionFactorOut, EmissionFactorPatch, ImprovementSuggestion, ImprovementsOut, PortionEntry, SummaryOut, UnknownItemOut, UserProfile

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["activities"])


@router.post("/activity", response_model=ActivityResponse, status_code=201)
def create_activity(payload: ActivityCreate, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return carbon_agent.process_activity(
            raw_text=payload.raw_text,
            user_id=user_id,
            db=db,
        )
    except Exception as exc:
        log.error("Error procesando actividad: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error del agente: {str(exc)}")


@router.get("/history", response_model=list[ActivityOut])
def get_history(limit: int = 200, date_from: Optional[str] = None, date_to: Optional[str] = None, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve el historial de actividades de un usuario, más reciente primero."""
    q = db.query(Activity).filter(Activity.user_id == user_id)
    if date_from:
        q = q.filter(Activity.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
    if date_to:
        q = q.filter(Activity.created_at < datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1))
    return q.order_by(Activity.created_at.desc()).limit(limit).all()


@router.delete("/history", status_code=204)
def delete_history(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Borra todo el historial del usuario (cascade elimina las emisiones asociadas)."""
    deleted = (
        db.query(Activity)
        .filter(Activity.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    log.info("Historial borrado: user=%s, %d actividades eliminadas", user_id, deleted)


@router.delete("/history/{activity_id}", status_code=204)
def delete_activity(activity_id: int, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
def patch_activity(activity_id: int, payload: ActivityPatch, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
def get_summary(period_days: int = 30, annual_goal_kg: int = 6000, date_from: Optional[str] = None, date_to: Optional[str] = None, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Resumen agregado de emisiones del usuario en los últimos N días o en un rango de fechas."""
    from collections import defaultdict

    if date_from and date_to:
        since = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        until = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        period_days = max((until - since).days, 1)
    else:
        since = datetime.now(timezone.utc) - timedelta(days=period_days)
        until = None

    q = db.query(Activity).filter(Activity.user_id == user_id, Activity.created_at >= since)
    if until:
        q = q.filter(Activity.created_at < until)
    activities = q.all()

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
def get_profile(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Devuelve el perfil del usuario guardado en memoria."""
    memory = MemoryService()
    data = memory.get_memory(user_id=user_id, db=db)
    return UserProfile(
        home_city=data.get("home_city"),
        work_place=data.get("work_place"),
        display_name=data.get("display_name"),
    )


@router.patch("/profile", response_model=UserProfile)
def update_profile(payload: UserProfile, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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


@router.get("/admin/unknown-items", response_model=list[UnknownItemOut])
def get_unknown_items(status: str = "pending", limit: int = 100, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Lists items flagged as unknown by users, for admin review."""
    from app.models.models import UnknownItem
    return (
        db.query(UnknownItem)
        .filter(UnknownItem.status == status)
        .order_by(UnknownItem.created_at.desc())
        .limit(limit)
        .all()
    )


@router.patch("/admin/unknown-items/{item_id}", response_model=UnknownItemOut)
def update_unknown_item_status(item_id: int, status: str, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Update the review status of an unknown item (pending → added | rejected)."""
    from app.models.models import UnknownItem
    item = db.query(UnknownItem).filter(UnknownItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if status not in ("pending", "added", "rejected"):
        raise HTTPException(status_code=400, detail="status must be pending, added, or rejected")
    item.status = status
    db.commit()
    db.refresh(item)
    return item


@router.delete("/admin/unknown-items/{item_id}", status_code=204)
def delete_unknown_item(item_id: int, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Delete a single unknown item permanently."""
    from app.models.models import UnknownItem
    item = db.query(UnknownItem).filter(UnknownItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()


@router.delete("/admin/unknown-items", status_code=204)
def batch_delete_unknown_items(ids: list[int], _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Delete multiple unknown items by ID."""
    from app.models.models import UnknownItem
    db.query(UnknownItem).filter(UnknownItem.id.in_(ids)).delete(synchronize_session=False)
    db.commit()


@router.get("/admin/factors", response_model=list[EmissionFactorOut])
def list_factors(search: str = "", _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """List all emission factors, optionally filtered by search term."""
    q = db.query(EmissionFactor)
    if search:
        term = f"%{search}%"
        q = q.filter(
            EmissionFactor.display_name.ilike(term) |
            EmissionFactor.category.ilike(term) |
            EmissionFactor.main_category.ilike(term)
        )
    return q.order_by(EmissionFactor.main_category, EmissionFactor.display_name).all()


@router.post("/admin/factors", response_model=EmissionFactorOut, status_code=201)
def create_factor(payload: EmissionFactorCreate, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Create a new emission factor and add it to the database."""
    existing = db.query(EmissionFactor).filter(EmissionFactor.category == payload.category).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Factor '{payload.category}' already exists")
    factor = EmissionFactor(**payload.model_dump())
    db.add(factor)
    db.commit()
    db.refresh(factor)
    log.info("Nuevo factor creado: %s (%.4f kg/%s)", payload.category, payload.factor_kg_co2e, payload.unit)
    return factor


@router.patch("/admin/factors/{factor_id}", response_model=EmissionFactorOut)
def update_factor(factor_id: int, payload: EmissionFactorPatch, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Update an existing emission factor (partial update)."""
    factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(factor, field, value)
    db.commit()
    db.refresh(factor)
    log.info("Factor actualizado: %s", factor.category)
    return factor


@router.delete("/admin/factors/{factor_id}", status_code=204)
def delete_factor(factor_id: int, _: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Delete an emission factor permanently."""
    factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    db.delete(factor)
    db.commit()
    log.info("Factor eliminado: %s", factor.category)


@router.get("/portions", response_model=list[PortionEntry])
def get_portions(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns portion defaults for all non-transport categories, with user overrides applied."""
    memory = MemoryService()
    user_portions = memory.get_portions(user_id=user_id, db=db)
    factor_map = {f["category"]: f for f in EMISSION_FACTORS}

    entries: list[PortionEntry] = []
    for category, default_qty in DEFAULT_PORTIONS.items():
        factor = factor_map.get(category)
        if not factor:
            continue
        entries.append(PortionEntry(
            category=category,
            display_name=factor["display_name"],
            unit=factor["unit"],
            default_quantity=default_qty,
            user_quantity=user_portions.get(category),
        ))
    return entries


@router.patch("/portions", response_model=list[PortionEntry])
def update_portions(payload: dict[str, float], user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """Saves user-defined default portions. Send only the categories you want to override."""
    memory = MemoryService()
    memory.set_portions(user_id=user_id, portions=payload, db=db)
    db.commit()
    return get_portions(user_id=user_id, db=db)


@router.get("/improvements", response_model=ImprovementsOut)
def get_improvements(period_days: int = 30, annual_goal_kg: int = 6000, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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


_UPDATABLE_FIELDS = [
    "main_category", "display_name", "unit", "factor_kg_co2e", "default_quantity",
    "source_name", "source_year", "source_type", "source_detail",
    "source_url", "notes",
]


@router.post("/admin/seed-upsert", dependencies=[Depends(get_admin_user)])
def seed_upsert(dry_run: bool = False, db: Session = Depends(get_db)):
    """
    Ejecuta el upsert de factores de emisión desde seed_data.py.

    Protegido con token (query param ?token= o cabecera X-Admin-Token).
    Añade ?dry_run=true para simular sin escribir en la BD.
    """
    existing: dict[str, EmissionFactor] = {
        f.category: f for f in db.query(EmissionFactor).all()
    }

    results: dict[str, list] = {"inserted": [], "updated": [], "skipped": []}

    for data in EMISSION_FACTORS:
        category = data["category"]

        if category not in existing:
            if not dry_run:
                db.add(EmissionFactor(**data))
            results["inserted"].append(category)
        else:
            record = existing[category]
            changes = {}
            for field in _UPDATABLE_FIELDS:
                new_val = data.get(field)
                old_val = getattr(record, field)
                if new_val != old_val:
                    changes[field] = {"old": old_val, "new": new_val}

            if changes:
                if not dry_run:
                    for field, vals in changes.items():
                        setattr(record, field, vals["new"])
                results["updated"].append({"category": category, "changes": changes})
            else:
                results["skipped"].append(category)

    if not dry_run:
        db.commit()

    log.info(
        "seed-upsert %s — insertados: %d, actualizados: %d, sin cambios: %d",
        "DRY-RUN" if dry_run else "COMMIT",
        len(results["inserted"]),
        len(results["updated"]),
        len(results["skipped"]),
    )

    return {
        "dry_run": dry_run,
        "inserted": len(results["inserted"]),
        "updated": len(results["updated"]),
        "skipped": len(results["skipped"]),
        "detail": results,
    }