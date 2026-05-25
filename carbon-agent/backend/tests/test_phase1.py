"""
Tests de Fase 1 — base de datos, seed y endpoints stub.

Ejecutar:
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.db.init_db import seed_emission_factors
from app.models.models import EmissionFactor
from main import app

# ── Base de datos en memoria para tests ──────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"  # in-memory, descartada al finalizar

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
    """Crea tablas antes de cada test y las elimina después."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    database = TestingSession()
    try:
        yield database
    finally:
        database.close()


# ── Tests de seed ────────────────────────────────────────────────────────────

class TestSeedEmissionFactors:
    def test_seed_inserts_factors(self, db):
        seed_emission_factors(db)
        count = db.query(EmissionFactor).count()
        assert count > 0, "El seed debe insertar al menos un factor"

    def test_seed_contains_transport(self, db):
        seed_emission_factors(db)
        factor = db.query(EmissionFactor).filter_by(category="coche_gasolina").first()
        assert factor is not None
        assert factor.factor_kg_co2e == pytest.approx(0.192)
        assert factor.unit == "km"

    def test_seed_is_idempotent(self, db):
        seed_emission_factors(db)
        count_first = db.query(EmissionFactor).count()
        seed_emission_factors(db)  # segunda llamada
        count_second = db.query(EmissionFactor).count()
        assert count_first == count_second, "El seed no debe duplicar registros"

    def test_all_factors_have_positive_values(self, db):
        seed_emission_factors(db)
        factors = db.query(EmissionFactor).all()
        for f in factors:
            assert f.factor_kg_co2e > 0, f"Factor {f.category} debe ser positivo"


# ── Tests de endpoints ───────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestActivityEndpoint:
    def test_post_activity_returns_201(self, client):
        response = client.post("/api/activity", json={"raw_text": "He conducido 10 km al trabajo"})
        assert response.status_code == 201

    def test_post_activity_persists_text(self, client):
        text = "Comí un filete de ternera"
        response = client.post("/api/activity", json={"raw_text": text})
        assert response.status_code == 201
        data = response.json()
        assert data["activity"]["raw_text"] == text

    def test_post_activity_returns_message(self, client):
        response = client.post("/api/activity", json={"raw_text": "Volé de Madrid a Barcelona"})
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    def test_post_activity_too_short_text_fails(self, client):
        response = client.post("/api/activity", json={"raw_text": "Hi"})
        assert response.status_code == 422


class TestHistoryEndpoint:
    def test_history_empty_initially(self, client):
        response = client.get("/api/history")
        assert response.status_code == 200
        assert response.json() == []

    def test_history_returns_posted_activities(self, client):
        client.post("/api/activity", json={"raw_text": "Cogí el metro 3 paradas"})
        client.post("/api/activity", json={"raw_text": "Compré un smartphone nuevo"})
        response = client.get("/api/history")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_history_ordered_most_recent_first(self, client):
        client.post("/api/activity", json={"raw_text": "Actividad primera"})
        client.post("/api/activity", json={"raw_text": "Actividad segunda"})
        data = client.get("/api/history").json()
        assert data[0]["raw_text"] == "Actividad segunda"


class TestSummaryEndpoint:
    def test_summary_zero_when_no_activities(self, client):
        response = client.get("/api/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_activities"] == 0
        assert data["total_kg_co2e"] == 0.0
