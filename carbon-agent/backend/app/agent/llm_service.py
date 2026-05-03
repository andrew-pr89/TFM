"""
Servicio LLM — wrapper compartido sobre la API de OpenAI.

Usado por:
  - Extractor:    convierte texto natural → actividades estructuradas (JSON)
  - Recomendador: genera recomendaciones personalizadas (texto)

Regla de arquitectura:
  Este servicio NUNCA recibe factores de emisión ni hace cálculos numéricos.
  Solo interpreta lenguaje natural y genera texto.
"""

import json
import logging
from typing import Any

from openai import OpenAI

from app.core.config import settings

log = logging.getLogger(__name__)


class LLMService:
    """Cliente OpenAI con métodos específicos para cada caso de uso del agente."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    # ── Método base ──────────────────────────────────────────────────────────

    def _chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Llamada base al modelo. Devuelve el texto de la respuesta."""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        log.debug("LLM response (%s tokens): %s", response.usage.total_tokens, content[:120])
        return content.strip()

    # ── Extracción ───────────────────────────────────────────────────────────

    def extract_activities(self, raw_text: str, valid_categories: list[str]) -> list[dict]:
        """
        Convierte texto libre en una lista de actividades estructuradas.

        Devuelve una lista de dicts con el esquema:
            [{"category": str, "quantity": float, "unit": str, "description": str}]

        El LLM solo identifica categoría y cantidad.
        El cálculo de emisiones se hace fuera de este servicio.
        """
        categories_str = "\n".join(f"  - {c}" for c in valid_categories)

        system = f"""Eres un extractor de actividades con huella de carbono.
Tu única tarea es analizar el texto del usuario e identificar actividades
que tengan impacto en CO₂, estructurándolas en JSON.

Categorías válidas (usa EXACTAMENTE estos identificadores):
{categories_str}

Responde ÚNICAMENTE con un array JSON válido, sin texto adicional, sin markdown.
Formato de cada elemento:
{{
  "category": "<categoría exacta de la lista>",
  "quantity": <número positivo>,
  "unit": "<unidad coherente con la categoría>",
  "description": "<descripción breve en español>"
}}

Si no encuentras ninguna actividad con impacto CO₂, devuelve: []
Si hay varias actividades en el texto, inclúyelas todas."""

        user = f"Texto del usuario: {raw_text}"

        raw = self._chat(system, user, temperature=0.1)

        # Limpiar posibles bloques markdown si el modelo los añade
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            result = json.loads(raw)
            if not isinstance(result, list):
                log.warning("LLM devolvió un no-array: %s", raw[:200])
                return []
            return result
        except json.JSONDecodeError:
            log.error("Error parseando JSON del LLM: %s", raw[:300])
            return []

    # ── Recomendación ────────────────────────────────────────────────────────

    def generate_recommendation(
        self,
        total_kg_co2e: float,
        activities_summary: list[dict],
        user_memory: dict[str, str],
    ) -> str:
        """
        Genera una recomendación personalizada basada en las emisiones calculadas.

        Recibe el total ya calculado (determinista) y genera solo el texto explicativo.
        """
        activities_text = "\n".join(
            f"  - {a['description']}: {a['amount_kg_co2e']:.3f} kg CO₂e"
            for a in activities_summary
        )

        memory_text = ""
        if user_memory:
            memory_text = "Contexto del usuario (hábitos previos):\n" + "\n".join(
                f"  - {k}: {v}" for k, v in user_memory.items()
            )

        system = """Eres un asistente de sostenibilidad ambiental.
Tu tarea es generar una recomendación breve, práctica y positiva
basada en las actividades y emisiones CO₂ registradas por el usuario.

Reglas:
- Máximo 3 frases.
- Tono motivador, no culpabilizador.
- Da una acción concreta y realista.
- Responde siempre en español."""

        user = f"""El usuario ha registrado las siguientes actividades hoy:
{activities_text}

Total de emisiones: {total_kg_co2e:.3f} kg CO₂e

{memory_text}

Genera una recomendación personalizada."""

        return self._chat(system, user, temperature=0.7)
