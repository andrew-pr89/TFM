"""
Schemas Pydantic — validación de entrada/salida en los endpoints.

Separados de los modelos ORM deliberadamente:
  - Los modelos ORM definen la estructura de la BD.
  - Los schemas definen los contratos de la API.
"""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field


# ── EmissionFactor ───────────────────────────────────────────────────────────

class EmissionFactorOut(BaseModel):
    id: int
    category: str
    main_category: str
    display_name: str
    unit: str
    factor_kg_co2e: float
    source: str | None

    model_config = {"from_attributes": True}


# ── Activity ─────────────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=1000, description="Texto libre del usuario")
    user_id: str = Field(default="default", max_length=100)


class EmissionOut(BaseModel):
    id: int
    factor: EmissionFactorOut
    quantity: float
    amount_kg_co2e: float

    model_config = {"from_attributes": True}


class ActivityOut(BaseModel):
    id: int
    user_id: str
    raw_text: str
    created_at: datetime
    emissions: list[EmissionOut] = []

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def main_category(self) -> str:
        """Devuelve la categoría principal de la actividad (la del factor con más CO₂)."""
        if not self.emissions:
            return "Desconocido"
        # Encontrar la emisión con mayor CO₂
        max_emission = max(self.emissions, key=lambda e: e.amount_kg_co2e)
        return max_emission.factor.main_category


# ── Respuesta de /activity (POST) ─────────────────────────────────────────────

class ActivityResponse(BaseModel):
    """Lo que devuelve POST /activity al cliente."""
    activity: ActivityOut
    total_kg_co2e: float
    recommendation: str
    is_question: bool = False


# ── Summary ───────────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    user_id: str
    total_activities: int
    total_kg_co2e: float
    top_categories: list[dict]          # [{category, total_kg_co2e}]
    period_days: int
