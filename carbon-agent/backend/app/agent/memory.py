"""
Memoria de usuario — guarda y recupera hábitos/preferencias.

En el MVP es una tabla clave-valor simple (UserMemory).
El Recomendador la consulta para personalizar sus sugerencias.
"""

import json
import logging

from sqlalchemy.orm import Session

from app.models.models import UserMemory

log = logging.getLogger(__name__)


class MemoryService:
    """Lee y actualiza los hábitos del usuario en la BD."""

    def get_memory(self, user_id: str, db: Session) -> dict[str, str]:
        """Devuelve todos los hábitos del usuario como dict {clave: valor}."""
        records = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
        return {r.key: r.value for r in records}

    def update_memory(
        self, user_id: str, updates: dict[str, str], db: Session
    ) -> None:
        """
        Actualiza o inserta hábitos del usuario.
        Upsert manual: si la clave existe la sobreescribe, si no la crea.
        """
        existing = {
            r.key: r
            for r in db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
        }

        for key, value in updates.items():
            if key in existing:
                existing[key].value = value
            else:
                db.add(UserMemory(user_id=user_id, key=key, value=value))

        db.flush()
        log.info("Memoria actualizada para user=%s: %s", user_id, list(updates.keys()))

    def get_home_city(self, user_id: str, db: Session) -> str | None:
        """Devuelve la ciudad de origen habitual del usuario, o None si no está guardada."""
        record = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key == "home_city")
            .first()
        )
        return record.value if record else None

    def set_home_city(self, user_id: str, city: str, db: Session) -> None:
        """Guarda la ciudad de origen habitual del usuario."""
        self.update_memory(user_id=user_id, updates={"home_city": city}, db=db)
        log.info("Ciudad de origen guardada para user=%s: %s", user_id, city)

    def get_work_place(self, user_id: str, db: Session) -> str | None:
        """Devuelve el lugar de trabajo del usuario, o None si no está guardado."""
        record = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key == "work_place")
            .first()
        )
        return record.value if record else None

    def get_pending_activity(self, user_id: str, db: Session) -> dict | None:
        """Devuelve la actividad pendiente de resolución (esperando más info), o None."""
        record = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key == "pending_activity")
            .first()
        )
        if record:
            try:
                return json.loads(record.value)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_pending_activity(
        self, user_id: str, category: str, description: str, question: str, db: Session,
        destination: str | None = None,
    ) -> None:
        """Guarda una actividad pendiente: esperamos que el usuario aporte la información faltante."""
        data: dict = {"category": category, "description": description, "question": question}
        if destination:
            data["destination"] = destination
        value = json.dumps(data)
        self.update_memory(user_id=user_id, updates={"pending_activity": value}, db=db)
        log.info("Actividad pendiente guardada para user=%s: %s", user_id, category)

    def clear_pending_activity(self, user_id: str, db: Session) -> None:
        """Elimina la actividad pendiente tras resolverla."""
        record = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key == "pending_activity")
            .first()
        )
        if record:
            db.delete(record)
            db.flush()
            log.info("Actividad pendiente eliminada para user=%s", user_id)

    def get_portions(self, user_id: str, db: Session) -> dict[str, float]:
        """Returns user-overridden portion sizes as {category: quantity}."""
        prefix = "portion_"
        records = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key.like(f"{prefix}%"))
            .all()
        )
        result: dict[str, float] = {}
        for r in records:
            category = r.key[len(prefix):]
            try:
                result[category] = float(r.value)
            except (ValueError, TypeError):
                pass
        return result

    def set_portions(self, user_id: str, portions: dict[str, float], db: Session) -> None:
        """Saves user-defined default portion sizes."""
        updates = {f"portion_{cat}": str(qty) for cat, qty in portions.items()}
        self.update_memory(user_id=user_id, updates=updates, db=db)

    def get_recurring(self, user_id: str, db: Session) -> dict[str, dict]:
        """Returns recurring activity config as {category: {quantity, enabled}}."""
        import json
        records = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.key.like("recurring_%"))
            .all()
        )
        result: dict[str, dict] = {}
        for r in records:
            if r.key == "recurring_last_applied":
                continue
            cat = r.key[len("recurring_"):]
            try:
                result[cat] = json.loads(r.value)
            except Exception:
                pass
        return result

    def set_recurring(self, user_id: str, updates: dict[str, dict], db: Session) -> None:
        import json
        self.update_memory(
            user_id=user_id,
            updates={f"recurring_{cat}": json.dumps(cfg) for cat, cfg in updates.items()},
            db=db,
        )

    def get_recurring_last_applied(self, user_id: str, db: Session) -> str | None:
        record = db.query(UserMemory).filter(
            UserMemory.user_id == user_id, UserMemory.key == "recurring_last_applied"
        ).first()
        return record.value if record else None

    def set_recurring_last_applied(self, user_id: str, date_str: str, db: Session) -> None:
        self.update_memory(user_id=user_id, updates={"recurring_last_applied": date_str}, db=db)

    def infer_habits(self, user_id: str, category: str, db: Session) -> None:
        """
        Infiere y guarda hábitos a partir de las actividades registradas.
        En el MVP registra el transporte más reciente usado.
        """
        transport_categories = {
            "coche_gasolina", "coche_diesel", "coche_electrico",
            "moto", "tren", "metro", "autobus",
        }

        if category in transport_categories:
            self.update_memory(
                user_id=user_id,
                updates={"transporte_habitual": category},
                db=db,
            )
