from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite necesita check_same_thread=False para funcionar con FastAPI
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.app_debug,  # muestra SQL en consola en desarrollo
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa compartida por todos los modelos ORM."""
    pass


def get_db():
    """Dependencia FastAPI: abre sesión, la cede, la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
