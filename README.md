# Carbon Agent MVP

Agente IA para registrar actividades personales y estimar huella de carbono.

## Stack
- **Frontend**: React + Vite
- **Backend**: Python 3.11+ · FastAPI · SQLAlchemy
- **Agente**: OpenAI API
- **Base de datos**: SQLite (MVP) → PostgreSQL (producción)

## Estructura

```
carbon-agent/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints FastAPI (routers)
│   │   ├── core/         # Configuración, settings
│   │   ├── db/           # Engine, session, init_db, seed
│   │   ├── models/       # Modelos SQLAlchemy (ORM)
│   │   └── schemas/      # Schemas Pydantic (request/response)
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
└── docs/
```

## Inicio rápido

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # añade tu OPENAI_API_KEY
python -m app.db.init_db        # crea tablas + seed de factores
uvicorn main:app --reload
```

API disponible en `http://localhost:8000`
Docs automáticas en `http://localhost:8000/docs`

## Regla de arquitectura clave

> El LLM **nunca** calcula emisiones. Solo interpreta texto natural y genera
> recomendaciones. Todo cálculo CO₂ es **determinista**: `cantidad × factor`.
