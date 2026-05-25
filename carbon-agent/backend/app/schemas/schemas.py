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
    source_name: str | None
    source_year: int | None
    source_type: str | None
    source_detail: str | None
    source_url: str | None
    notes: str | None

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
    description: str | None = None

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
    message: str                            # recomendación o pregunta aclaratoria según is_question
    is_question: bool = False
    clarifying_question: str | None = None  # pregunta pendiente cuando hay emisiones Y actividad incompleta


# ── User profile ─────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    home_city: str | None = None       # ciudad de residencia
    work_place: str | None = None      # lugar de trabajo / centro de estudios
    display_name: str | None = None    # nombre del usuario (opcional)


# ── Activity patch ───────────────────────────────────────────────────────────

class ActivityPatch(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=1000)
    created_at: datetime | None = None


# ── Improvements ─────────────────────────────────────────────────────────────

class ImprovementSuggestion(BaseModel):
    category: str
    current_kg: float
    pct_of_total: float
    action: str
    tip: str
    potential_saving_pct: int


class ImprovementsOut(BaseModel):
    suggestions: list[ImprovementSuggestion]
    total_kg: float
    budget_kg: float
    period_days: int


# ── Summary ───────────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    user_id: str
    total_activities: int
    total_kg_co2e: float
    top_categories: list[dict]          # [{category, total_kg_co2e}]
    period_days: int
    budget_kg_co2e: float               # presupuesto sostenible IPCC (2 t/año prorrateado)
