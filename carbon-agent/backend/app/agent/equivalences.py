"""
Equivalencias cotidianas para cifras de CO2e.

Regla de arquitectura (misma que llm_service.py): el cálculo es 100%
determinista, usando los factores de emisión ya almacenados en BD.
El LLM nunca calcula estas cifras — solo las redacta en lenguaje natural
a partir del resultado que le pasamos aquí.
"""

from sqlalchemy.orm import Session

from app.models.models import EmissionFactor

# Velocidad media asumida para convertir km en coche a minutos de conducción
# (mezcla urbana/interurbana, España). El tiempo se entiende más rápido que
# la distancia, así que expresamos el coche en minutos en vez de km.
_AVG_CAR_SPEED_KMH = 50.0

# Categorías de referencia usadas para expresar una cifra de CO2e como
# algo cotidiano y tangible. (category en BD, etiqueta en texto)
_REFERENCE_CATEGORIES = [
    ("coche_gasolina", "minutos conduciendo"),
    ("television", "horas de televisión"),
]


def compute_equivalences(total_kg_co2e: float, db: Session, limit: int = 2) -> list[dict]:
    """
    Devuelve equivalencias tipo [{"label": "minutos conduciendo", "amount": 36}]
    a partir del factor kg/unidad de categorías de referencia reales.
    Si un factor no existe en BD, se omite esa entrada.
    """
    if total_kg_co2e <= 0:
        return []

    equivalences: list[dict] = []
    for category, label in _REFERENCE_CATEGORIES:
        factor = db.query(EmissionFactor).filter_by(category=category).first()
        if not factor or not factor.factor_kg_co2e:
            continue

        amount = total_kg_co2e / factor.factor_kg_co2e  # unidad nativa del factor (km, horas...)

        if category == "coche_gasolina":
            amount = round(amount / _AVG_CAR_SPEED_KMH * 60)  # km → minutos
        else:
            amount = round(amount, 1)

        equivalences.append({"label": label, "amount": amount})
        if len(equivalences) >= limit:
            break
    return equivalences
