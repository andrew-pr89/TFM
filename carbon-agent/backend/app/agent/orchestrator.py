"""
Orquestador del agente — coordina todos los componentes.
"""

import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.calculator import CO2Calculator
from app.agent.extractor import DEFAULT_PORTIONS, Extractor, ExtractedActivity
from app.agent.llm_service import LLMService
from app.agent.memory import MemoryService
from app.models.models import Activity
from app.schemas.schemas import ActivityOut, ActivityResponse

log = logging.getLogger(__name__)

_MONTHS_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
_WEEKDAYS_ES = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
    'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6,
}


def _detect_activity_date(raw_text: str, today_iso: str) -> str | None:
    """Detect Spanish temporal expressions and return ISO date, or None if today."""
    try:
        today_date = date.fromisoformat(today_iso)
    except ValueError:
        return None

    t = raw_text.lower()

    if re.search(r'\bayer\b', t):
        return (today_date - timedelta(days=1)).isoformat()

    if re.search(r'\banteayer\b', t):
        return (today_date - timedelta(days=2)).isoformat()

    # "el lunes pasado", "el martes", etc.
    for name, dow in _WEEKDAYS_ES.items():
        if re.search(rf'\b{name}\b', t):
            days_back = (today_date.weekday() - dow) % 7
            if days_back == 0:
                days_back = 7
            return (today_date - timedelta(days=days_back)).isoformat()

    # "el 4 de abril", "el 15 de junio de 2025"
    m = re.search(r'\b(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?', t)
    if m:
        day, month_name, year_str = int(m.group(1)), m.group(2), m.group(3)
        if month_name in _MONTHS_ES:
            month = _MONTHS_ES[month_name]
            year = int(year_str) if year_str else today_date.year
            try:
                candidate = date(year, month, day)
                if candidate > today_date:
                    candidate = date(year - 1, month, day)
                if candidate < today_date:
                    return candidate.isoformat()
            except ValueError:
                pass

    return None


def _empty(user_id: str, raw_text: str) -> ActivityResponse:
    return ActivityResponse(
        activity=ActivityOut(
            id=-1,
            user_id=user_id,
            raw_text=raw_text,
            created_at=datetime.now(timezone.utc),
            emissions=[],
        ),
        total_kg_co2e=0.0,
        message="",
    )


class CarbonAgent:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.extractor = Extractor(llm=self.llm)
        self.calculator = CO2Calculator()
        self.memory = MemoryService()

    def process_activity(self, raw_text: str, user_id: str, db: Session) -> ActivityResponse:

        today = datetime.now(timezone.utc).date().isoformat()

        # Detect temporal expressions in plain Python — more reliable than LLM
        activity_date_str: str | None = _detect_activity_date(raw_text, today)
        if activity_date_str:
            log.info("Fecha detectada por regex: %s para '%s'", activity_date_str, raw_text[:60])

        # ── 1. Cargar contexto de memoria antes de extraer ───────────────────
        home_city = self.memory.get_home_city(user_id=user_id, db=db)
        work_place = self.memory.get_work_place(user_id=user_id, db=db)
        existing_pending_activity = self.memory.get_pending_activity(user_id=user_id, db=db)

        # If the pending activity is a food/energy category that now has a default portion,
        # auto-clear it so the extractor processes all items in the message normally.
        if existing_pending_activity:
            pending_cat = existing_pending_activity.get("category", "")
            if pending_cat in DEFAULT_PORTIONS:
                self.memory.clear_pending_activity(user_id=user_id, db=db)
                db.commit()
                existing_pending_activity = None

        user_portions = self.memory.get_portions(user_id=user_id, db=db)

        # ── 2. Extracción (LLM) — ANTES de persistir ────────────────────────
        extracted = self.extractor.extract(
            raw_text=raw_text,
            db=db,
            home_city=home_city,
            work_place=work_place,
            pending_activity=existing_pending_activity,
            user_portions=user_portions or None,
            user_id=user_id,
            today=today,
        )

        # ── Separar marcadores especiales de actividades reales ──────────────
        new_home_city: str | None = None
        new_pending_activity: dict | None = None
        pending_question: str | None = None
        # activity_date_str already set by regex above; LLM marker is a fallback

        unknown_names: list[str] = []
        filtered = []
        for item in extracted:
            if isinstance(item, dict) and "set_home_city" in item:
                new_home_city = item["set_home_city"]
            elif isinstance(item, dict) and "set_activity_date" in item:
                if not activity_date_str:  # regex takes precedence
                    activity_date_str = item["set_activity_date"]
            elif isinstance(item, dict) and "set_pending_activity" in item:
                new_pending_activity = item["set_pending_activity"]
            elif isinstance(item, dict) and "clarifying_question" in item:
                pending_question = item["clarifying_question"]
            elif isinstance(item, dict) and "unknown_items" in item:
                unknown_names = item["unknown_items"]
            else:
                filtered.append(item)
        extracted = filtered

        # Guardar home_city si el LLM la detectó
        if new_home_city:
            self.memory.set_home_city(user_id=user_id, city=new_home_city, db=db)
            db.commit()
            log.info("home_city guardada para user=%s: %s", user_id, new_home_city)

        # Si el turno actual RESOLVIÓ el pending_activity anterior → limpiarlo.
        # Solo se considera resuelto si hay actividades de la misma categoría calculadas.
        pending_resolved = (
            existing_pending_activity
            and not new_pending_activity
            and any(
                isinstance(e, ExtractedActivity)
                and e.category == existing_pending_activity.get("category")
                for e in extracted
            )
        )
        if pending_resolved:
            self.memory.clear_pending_activity(user_id=user_id, db=db)
            db.commit()

        # Si hay nuevo transporte pendiente de ubicación → guardarlo
        if new_pending_activity:
            self.memory.set_pending_activity(
                user_id=user_id,
                category=new_pending_activity["category"],
                description=new_pending_activity["description"],
                question=new_pending_activity.get("question", ""),
                destination=new_pending_activity.get("destination"),
                db=db,
            )
            db.commit()

        # ── Caso: solo pregunta (sin actividades calculables aún) ─────────────
        if pending_question and not extracted:
            log.info("Pregunta aclaratoria para user=%s: %s", user_id, pending_question)
            response = _empty(user_id, raw_text)
            response.message = pending_question
            response.is_question = True
            return response

        # ── Caso: solo se declaró ciudad de origen ────────────────────────────
        if not extracted and not pending_question and new_home_city:
            still_pending = self.memory.get_pending_activity(user_id=user_id, db=db)
            follow_up = (
                f" Ahora dime: {still_pending['description']} — ¿desde qué lugar y hasta dónde?"
                if still_pending else ""
            )
            response = _empty(user_id, raw_text)
            response.message = (
                f"¡Perfecto! He guardado {new_home_city} como tu ciudad de origen. "
                f"La usaré automáticamente para calcular distancias cuando viajes.{follow_up}"
            )
            response.is_question = bool(follow_up)
            return response

        # ── Caso: nada identificado ──────────────────────────────────────────
        if not extracted and not pending_question:
            log.info("Nada que guardar — el LLM no identificó actividades CO₂.")
            if unknown_names:
                db.commit()  # persist unknown items stored during extraction
            response = _empty(user_id, raw_text)
            if unknown_names:
                names_str = ", ".join(f'"{n}"' for n in unknown_names)
                es_varios = len(unknown_names) > 1
                response.message = (
                    f"No tengo datos de huella de carbono para {names_str}. "
                    f"{'Lo he' if not es_varios else 'Los he'} anotado para añadirlo{'s' if es_varios else ''} al catálogo pronto."
                )
            else:
                response.message = (
                    "No he podido identificar actividades con huella de carbono en tu mensaje. "
                    "Prueba con algo como: 'he conducido 20 km', 'comí 200g de ternera' "
                    "o 'vuelo Madrid-Londres de 600 km'."
                )
            return response

        # ── 2. Persistir Activity ────────────────────────────────────────────
        activity = Activity(user_id=user_id, raw_text=raw_text)
        db.add(activity)
        db.flush()  # generates ID via autoincrement

        if activity_date_str:
            try:
                override_dt = datetime.fromisoformat(activity_date_str).replace(tzinfo=timezone.utc)
                # Use execute to bypass SQLAlchemy's server_default tracking
                db.execute(
                    text("UPDATE activities SET created_at = :ts WHERE id = :id"),
                    {"ts": override_dt.strftime("%Y-%m-%d %H:%M:%S"), "id": activity.id},
                )
                db.expire(activity)  # force reload on next access
                log.info("Fecha de actividad sobreescrita: %s para user=%s id=%s", activity_date_str, user_id, activity.id)
            except Exception as exc:
                log.warning("No se pudo sobreescribir created_at: %s", exc)

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

        # Si sigue habiendo un transporte pendiente en memoria (no resuelto este turno), recordarlo
        still_pending = None if pending_resolved else self.memory.get_pending_activity(user_id=user_id, db=db)
        if still_pending and not pending_question:
            pending_question = (
                f"Todavía me falta saber los lugares para "
                f"{still_pending.get('description', 'el transporte pendiente')}: "
                "¿desde qué lugar y hasta dónde?"
            )

        # Append unknown items note to the recommendation if any were flagged
        if unknown_names:
            names_str = ", ".join(f'"{n}"' for n in unknown_names)
            es_varios = len(unknown_names) > 1
            recommendation += (
                f"\n\n⚠️ No tengo datos para {names_str} — "
                f"{'lo he' if not es_varios else 'los he'} anotado para añadirlo{'s' if es_varios else ''} al catálogo."
            )

        log.info("Actividad procesada: user=%s total=%.3f kg CO₂e", user_id, total)

        return ActivityResponse(
            activity=ActivityOut.model_validate(activity),
            total_kg_co2e=total,
            message=recommendation,
            clarifying_question=pending_question or None,
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
            if not (isinstance(e, dict) and (
                "clarifying_question" in e or "set_home_city" in e
                or "set_pending_activity" in e or "set_activity_date" in e
            ))
        ]
        if extracted:
            self.calculator.calculate(activity=activity, extracted_activities=extracted, db=db)

        db.commit()
        db.refresh(activity)
        return ActivityOut.model_validate(activity)


carbon_agent = CarbonAgent()