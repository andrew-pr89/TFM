"""
Punto de entrada de la aplicación FastAPI.

Arranca con:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.activities import router as activities_router
from app.core.config import settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD al arrancar la aplicación."""
    init_db()
    yield


app = FastAPI(
    title="Carbon Agent API",
    description="Agente IA para registrar actividades y estimar huella de carbono.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — orígenes permitidos: dev local + frontend(s) de producción
_origins = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"]

# Soporta lista separada por comas: "https://a.railway.app,https://b.vercel.app"
if settings.frontend_url:
    for url in settings.frontend_url.split(","):
        url = url.strip()
        if url:
            _origins.append(url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.up\.railway\.app",  # cualquier subdominio Railway
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(activities_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
