"""
Tests de Fase 2 — Extractor, Calculadora y flujo completo del agente.

Los tests del LLM usan mocks para no consumir créditos de OpenAI.
Los tests de la Calculadora son puramente unitarios (sin BD ni LLM).

Ejecutar:
    pytest tests/ -v
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.calculator import CO2Calculator
from app.agent.extractor import ExtractedActivity, Extractor
from app.db.database import Base, get_db
from app.db.init_db import seed_emission_factors
from app.models.models import Activity, EmissionFactor
from main import app

# ── BD en memoria para tests ─────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()
    seed_emission_factors(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    database = TestingSession()
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def client():
    return TestClient(app)


# ── Tests Calculadora CO₂ (puramente unitarios) ───────────────────────────────

class TestCO2Calculator:
    def _make_factor(self, category: str, factor: float, unit: str = "km") -> EmissionFactor:
        f = EmissionFactor()
        f.id = 1
        f.category = category
        f.display_name = category
        f.unit = unit
        f.factor_kg_co2e = factor
        return f

    def _make_activity(self) -> Activity:
        a = Activity()
        a.id = 1
        a.user_id = "test"
        a.raw_text = "test"
        return a

    def test_calculation_is_deterministic(self, db):
        calc = CO2Calculator()
        factor = self._make_factor("coche_gasolina", 0.192)
        activity = self._make_activity()

        extracted = [ExtractedActivity(
            category="coche_gasolina",
            quantity=10.0,
            unit="km",
            description="Coche al trabajo",
            factor=factor,
        )]

        results = calc.calculate(activity, extracted, db)
        assert len(results) == 1
        assert results[0].amount_kg_co2e == pytest.approx(1.92, rel=1e-5)

    def test_formula_quantity_times_factor(self, db):
        calc = CO2Calculator()
        factor = self._make_factor("carne_vacuno", 27.0, unit="kg")
        activity = self._make_activity()

        extracted = [ExtractedActivity(
            category="carne_vacuno",
            quantity=0.5,
            unit="kg",
            description="Filete",
            factor=factor,
        )]

        results = calc.calculate(activity, extracted, db)
        assert results[0].amount_kg_co2e == pytest.approx(13.5, rel=1e-5)

    def test_total_sums_multiple_activities(self, db):
        calc = CO2Calculator()
        activity = self._make_activity()

        f1 = self._make_factor("coche_gasolina", 0.192)
        f2 = self._make_factor("carne_vacuno", 27.0)
        f2.id = 2

        extracted = [
            ExtractedActivity("coche_gasolina", 10.0, "km", "Coche", f1),
            ExtractedActivity("carne_vacuno", 0.3, "kg", "Carne", f2),
        ]

        results = calc.calculate(activity, extracted, db)
        total = CO2Calculator.total(results)
        expected = round(10.0 * 0.192 + 0.3 * 27.0, 3)
        assert total == pytest.approx(expected, rel=1e-4)

    def test_llm_never_involved_in_calculation(self, db):
        """La calculadora no debe tener ninguna referencia al LLM."""
        import inspect
        from app.agent import calculator
        source = inspect.getsource(calculator)
        assert "openai" not in source.lower()
        assert "llm" not in source.lower()
        assert "gpt" not in source.lower()


# ── Tests Extractor (con LLM mockeado) ───────────────────────────────────────

class TestExtractor:
    def test_extractor_validates_unknown_category(self, db):
        mock_llm = MagicMock()
        mock_llm.extract_activities.return_value = [
            {"category": "categoria_inventada", "quantity": 10, "unit": "km", "description": "test"}
        ]
        extractor = Extractor(llm=mock_llm)
        result = extractor.extract("texto cualquiera", db)
        assert result == [], "Categorías desconocidas deben ser ignoradas"

    def test_extractor_validates_negative_quantity(self, db):
        mock_llm = MagicMock()
        mock_llm.extract_activities.return_value = [
            {"category": "coche_gasolina", "quantity": -5, "unit": "km", "description": "test"}
        ]
        extractor = Extractor(llm=mock_llm)
        result = extractor.extract("texto cualquiera", db)
        assert result == [], "Cantidades negativas deben ser ignoradas"

    def test_extractor_resolves_factor_from_db(self, db):
        mock_llm = MagicMock()
        mock_llm.extract_activities.return_value = [
            {"category": "coche_gasolina", "quantity": 15.0, "unit": "km", "description": "Al trabajo"}
        ]
        extractor = Extractor(llm=mock_llm)
        result = extractor.extract("He conducido 15 km", db)
        assert len(result) == 1
        assert result[0].category == "coche_gasolina"
        assert result[0].quantity == 15.0
        assert result[0].factor.factor_kg_co2e == pytest.approx(0.192)

    def test_extractor_handles_empty_llm_response(self, db):
        mock_llm = MagicMock()
        mock_llm.extract_activities.return_value = []
        extractor = Extractor(llm=mock_llm)
        result = extractor.extract("hoy ha sido un buen día", db)
        assert result == []


# ── Tests endpoint POST /activity (agente mockeado) ───────────────────────────

class TestActivityEndpointWithAgent:
    def test_post_activity_returns_co2_total(self, client):
        from app.schemas.schemas import ActivityOut, ActivityResponse
        from datetime import datetime

        mock_response = ActivityResponse(
            activity=ActivityOut(
                id=1, user_id="default", raw_text="He conducido 10 km",
                created_at=datetime.utcnow(), emissions=[]
            ),
            total_kg_co2e=1.92,
            message="Considera usar el transporte público mañana.",
        )

        with patch("app.agent.orchestrator.carbon_agent.process_activity", return_value=mock_response):
            response = client.post("/api/activity", json={"raw_text": "He conducido 10 km"})

        assert response.status_code == 201
        data = response.json()
        assert data["total_kg_co2e"] == 1.92
        assert len(data["message"]) > 0

    def test_post_activity_500_on_agent_error(self, client):
        with patch(
            "app.agent.orchestrator.carbon_agent.process_activity",
            side_effect=Exception("OpenAI timeout")
        ):
            response = client.post("/api/activity", json={"raw_text": "He conducido 10 km"})

        assert response.status_code == 500
