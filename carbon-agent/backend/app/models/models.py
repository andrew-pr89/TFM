"""
Modelos ORM — mapean directamente a tablas SQLite.

Tablas:
  emission_factors   — factores de emisión estáticos (seed, no los toca el LLM)
  activities         — registro de actividades del usuario (texto crudo + metadatos)
  emissions          — resultado del cálculo CO₂ por actividad (determinista)
  user_memory        — hábitos/preferencias recordadas del usuario
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class EmissionFactor(Base):
    """
    Factor de emisión por categoría y unidad.
    Datos estáticos — se cargan en seed y no se modifican en runtime.

    Ejemplo:
        category='coche_gasolina', unit='km', factor_kg_co2e=0.192
        → conducir 10 km = 1.92 kg CO₂e
    """

    __tablename__ = "emission_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    main_category: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    factor_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=True)
    source_year: Mapped[int] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=True)    # official | scientific_literature | estimated
    source_detail: Mapped[str] = mapped_column(String(300), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    default_quantity: Mapped[float] = mapped_column(Float, nullable=True)  # ración estándar admin-configurable

    emissions: Mapped[list["Emission"]] = relationship(
        "Emission", back_populates="factor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmissionFactor {self.category} {self.factor_kg_co2e} kg/{self.unit}>"


class Activity(Base):
    """
    Registro de una actividad del usuario tal como la recibe el backend.
    Guarda el texto original para trazabilidad.
    """

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False, default="default")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)             # texto original del usuario
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    emissions: Mapped[list["Emission"]] = relationship(
        "Emission", back_populates="activity", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Activity id={self.id} user={self.user_id} text='{self.raw_text[:40]}'>"


class Emission(Base):
    """
    Resultado del cálculo CO₂ para una actividad concreta.

    El campo amount_kg_co2e es SIEMPRE el resultado de:
        quantity × factor_kg_co2e

    Nunca se obtiene de un LLM.
    """

    __tablename__ = "emissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("emission_factors.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    amount_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    activity: Mapped["Activity"] = relationship("Activity", back_populates="emissions")
    factor: Mapped["EmissionFactor"] = relationship("EmissionFactor", back_populates="emissions")

    def __repr__(self) -> str:
        return f"<Emission activity={self.activity_id} {self.amount_kg_co2e:.3f} kg CO₂e>"


class UserMemory(Base):
    """
    Hábitos y preferencias del usuario que el Recomendador usa como contexto.
    En el MVP es una tabla simple clave-valor por usuario.
    """

    __tablename__ = "user_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)           # p.ej. "transporte_habitual"
    value: Mapped[str] = mapped_column(Text, nullable=False)                # p.ej. "coche_gasolina"
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserMemory user={self.user_id} {self.key}={self.value}>"


class UnknownItem(Base):
    """
    Items mentioned by users that couldn't be mapped to a known emission category.
    Queued for admin review so new categories can be added to the catalog.
    """

    __tablename__ = "unknown_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    raw_term: Mapped[str] = mapped_column(String(300), nullable=False)   # exact word/phrase the user said
    context: Mapped[str] = mapped_column(Text, nullable=True)            # full original message
    guessed_category: Mapped[str] = mapped_column(String(100), nullable=True)  # LLM's best guess
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | added | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UnknownItem '{self.raw_term}' status={self.status}>"
