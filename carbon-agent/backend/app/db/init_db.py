"""
Inicialización de la base de datos.

Uso:
    python -m app.db.init_db

Crea todas las tablas (si no existen) y carga los factores de emisión.
Es idempotente: si los factores ya existen, no los duplica.
"""

import logging

from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.db.seed_data import EMISSION_FACTORS
from app.models.models import EmissionFactor  # importar modelos registra metadatos en Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def create_tables() -> None:
    """Crea todas las tablas definidas en los modelos ORM."""
    log.info("Creando tablas en %s …", engine.url)
    Base.metadata.create_all(bind=engine)
    log.info("Tablas creadas correctamente.")


def seed_emission_factors(db: Session) -> None:
    """
    Carga los factores de emisión iniciales.
    Usa upsert manual: inserta si la categoría no existe, omite si ya existe.
    """
    existing = {f.category for f in db.query(EmissionFactor.category).all()}
    new_factors = [f for f in EMISSION_FACTORS if f["category"] not in existing]

    if not new_factors:
        log.info("Factores de emisión ya presentes — nada que insertar.")
        return

    for data in new_factors:
        db.add(EmissionFactor(**data))

    db.commit()
    log.info("Insertados %d factores de emisión.", len(new_factors))


def init_db() -> None:
    create_tables()
    db = SessionLocal()
    try:
        seed_emission_factors(db)
    finally:
        db.close()
    log.info("Base de datos lista.")


if __name__ == "__main__":
    init_db()
