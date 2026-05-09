"""
Punto de entrada de la aplicación FastAPI.

Arranca con:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.activities import router as activities_router
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

# CORS — en desarrollo permite el dev server de React (puerto 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
