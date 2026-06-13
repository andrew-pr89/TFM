"""
Actualización de factores de emisión en producción.

Uso desde la consola de Railway:
    python update_seed.py            # upsert completo (inserta nuevos + actualiza existentes)
    python update_seed.py --dry-run  # muestra qué cambiaría sin tocar la BD
    python update_seed.py --stats    # solo muestra resumen del estado actual

Lógica:
  - INSERT si la categoría no existe
  - UPDATE si algún campo ha cambiado (factor, fuente, notas…)
  - SKIP si los datos son idénticos

No elimina factores que ya no estén en seed_data.py (seguridad).
"""

import argparse
import logging
import os
import sys

# ── Importaciones del proyecto ─────────────────────────────────────────────
# Añade la raíz del proyecto al path para poder importar app.*
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.seed_data import EMISSION_FACTORS
from app.models.models import EmissionFactor

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Campos que se comparan y actualizan (excluye 'id' y 'category')
UPDATABLE_FIELDS = [
    "main_category",
    "display_name",
    "unit",
    "factor_kg_co2e",
    "source_name",
    "source_year",
    "source_type",
    "source_detail",
    "source_url",
    "notes",
]


def get_engine():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Intenta cargar desde el config del proyecto
        try:
            from app.core.config import settings
            database_url = settings.database_url
        except Exception:
            pass
    if not database_url:
        log.error("No se encontró DATABASE_URL. Define la variable de entorno o el config del proyecto.")
        sys.exit(1)

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(database_url, connect_args=connect_args)


def run_upsert(dry_run: bool = False) -> dict:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    results = {"inserted": [], "updated": [], "skipped": []}

    try:
        # Carga todos los factores existentes indexados por category
        existing: dict[str, EmissionFactor] = {
            f.category: f for f in db.query(EmissionFactor).all()
        }

        for data in EMISSION_FACTORS:
            category = data["category"]

            if category not in existing:
                # ── INSERT ──────────────────────────────────────────────
                if not dry_run:
                    db.add(EmissionFactor(**data))
                results["inserted"].append(category)

            else:
                # ── UPDATE si hay diferencias ────────────────────────────
                record = existing[category]
                changes = {}
                for field in UPDATABLE_FIELDS:
                    new_val = data.get(field)
                    old_val = getattr(record, field)
                    if new_val != old_val:
                        changes[field] = (old_val, new_val)

                if changes:
                    if not dry_run:
                        for field, (_, new_val) in changes.items():
                            setattr(record, field, new_val)
                    results["updated"].append((category, changes))
                else:
                    results["skipped"].append(category)

        if not dry_run:
            db.commit()
            log.info("Commit realizado.")

    except Exception as e:
        db.rollback()
        log.error("Error durante el upsert: %s", e)
        raise
    finally:
        db.close()

    return results


def print_stats():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        total = db.query(EmissionFactor).count()
        from sqlalchemy import func
        by_cat = (
            db.query(EmissionFactor.main_category, func.count())
            .group_by(EmissionFactor.main_category)
            .order_by(func.count().desc())
            .all()
        )
        log.info("── Estado actual de emission_factors ──────────────────")
        log.info("Total: %d factores", total)
        for cat, count in by_cat:
            log.info("  %-20s %d", cat, count)
        log.info("────────────────────────────────────────────────────────")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Actualiza factores de emisión en la BD")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin escribir en la BD")
    parser.add_argument("--stats", action="store_true", help="Muestra resumen del estado actual y sale")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    mode = "DRY-RUN" if args.dry_run else "PRODUCCIÓN"
    log.info("── update_seed.py — modo %s ─────────────────────────────", mode)
    log.info("Factores en seed_data.py: %d", len(EMISSION_FACTORS))

    results = run_upsert(dry_run=args.dry_run)

    # ── Resumen ────────────────────────────────────────────────────────────
    log.info("")
    log.info("── Resultado ───────────────────────────────────────────────")
    log.info("  Insertados : %d", len(results["inserted"]))
    log.info("  Actualizados: %d", len(results["updated"]))
    log.info("  Sin cambios : %d", len(results["skipped"]))

    if results["inserted"]:
        log.info("")
        log.info("  Nuevos factores:")
        for cat in results["inserted"]:
            log.info("    + %s", cat)

    if results["updated"]:
        log.info("")
        log.info("  Factores modificados:")
        for cat, changes in results["updated"]:
            log.info("    ~ %s", cat)
            for field, (old, new) in changes.items():
                log.info("        %s: %r → %r", field, old, new)

    if args.dry_run:
        log.info("")
        log.info("  [DRY-RUN] No se ha escrito nada en la BD.")

    log.info("────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
