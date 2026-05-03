"""
Memoria de usuario — guarda y recupera hábitos/preferencias.

En el MVP es una tabla clave-valor simple (UserMemory).
El Recomendador la consulta para personalizar sus sugerencias.
"""

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
