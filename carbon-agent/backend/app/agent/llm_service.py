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

    def extract_activities(self, raw_text: str, factors_info: list[dict]) -> list[dict]:
        """
        Convierte texto libre en una lista de actividades estructuradas.

        Devuelve una lista de dicts con el esquema:
            [{"category": str, "quantity": float, "unit": str, "description": str}]

        El LLM solo identifica categoría y cantidad.
        El cálculo de emisiones se hace fuera de este servicio.
        """
        categories_str = "\n".join(
            f"  - {f['category']}  →  {f['display_name']}  [unidad: {f['unit']}]"
            for f in factors_info
        )

        system = f"""Eres un extractor de actividades con huella de carbono.
Tu tarea es analizar el texto del usuario e identificar TODAS las actividades
que tengan impacto en CO₂. Puede haber una o varias en el mismo mensaje.

Categorías válidas con su unidad de medida (usa EXACTAMENTE estos identificadores):
{categories_str}

REGLAS CRÍTICAS:

1. CANTIDAD EXPLÍCITA: Solo hay cantidad si el usuario escribe un NÚMERO (o "un/una")
   seguido de una unidad reconocida ("200g", "0.3 kg", "5 km", "2 kWh", "un vaso", "2 vasos").
   Unidades de referencia aceptadas:
   - "vaso" / "vasos" → 1 vaso = 0.25 litros (convierte directamente)
   "Un filete", "una hamburguesa", "algo de carne" NO son cantidades — falta la unidad.

2. CONVERSIÓN DE UNIDADES: devuelve siempre en la unidad del factor.
   - "200 gramos" con factor en kg → quantity=0.2
   - "500 ml" con factor en litro → quantity=0.5
   - "5 km" con factor en km → quantity=5
   - "1 vaso", "un vaso" con factor en litro → quantity=0.25  (1 vaso = 250 ml)
   - "2 vasos" con factor en litro → quantity=0.5

3. MÚLTIPLES ACTIVIDADES: El usuario puede mencionar varias acciones en un mismo mensaje.
   Identifica TODAS y devuélvelas en el array "activities", cada una con su propio estado.

POR CADA ACTIVIDAD IDENTIFICADA sigue esta lógica:

PASO 1: ¿Se puede asociar SEMÁNTICAMENTE a alguna categoría?
- Usa coincidencias semánticas, NO solo literales. Ejemplos orientativos:
  - "yogurt", "nata", "mantequilla", "batido lácteo" → lacteos_leche
  - "pasta", "espagueti", "macarrones", "fideos", "pan", "tostadas" → cereales
  - "lentejas", "garbanzos", "judías", "alubias", "guisantes" → legumbres
  - "plátano", "manzana", "naranja", "fresas", "uvas", "fruta" → fruta
  - "patatas fritas", "puré de patata" → patata
  - "hamburguesa casera", "pizza" → comida_rapida
  - "café solo", "café con leche" → cafe (y lacteos_leche si lleva leche)
  - "zumo de naranja" → zumo
  - "agua mineral" → agua_embotellada
  - "cerveza", "caña" → alcohol_cerveza
  - "vino", "copa de vino" → alcohol_vino
  - "refresco", "coca-cola", "fanta" → refresco_lata
- Si NO hay ninguna categoría relacionada → omite esta actividad (no la incluyas)
- Si SÍ → Ir al PASO 2

PASO 2: ¿Hay un NÚMERO (o "un/una") con una unidad reconocida?
- Unidades reconocidas: números con g/kg/km/kWh/litros/ml/horas/unidades/vaso/vasos
- Si SÍ → actividad completa con quantity y unit convertidos a la unidad del factor
- Si NO → Ir al PASO 3

PASO 3: Categoría identificada pero falta cantidad.
- SUBCASO A: Unidad "km" Y el usuario menciona DOS ciudades/municipios reales (ej: "Madrid", "Barcelona"):
  → actividad con quantity=null, origin="<ciudad>", destination="<ciudad>"
  → IMPORTANTE: "casa", "trabajo", "oficina", "hotel", "gimnasio", "colegio", "supermercado" NO son ciudades.
- SUBCASO B: Unidad "km" Y el usuario menciona solo UNA ciudad real (solo destino, sin origen):
  → actividad con quantity=null, origin=null, destination="<ciudad>", clarifying_question="¿Desde qué ciudad saliste? La recordaré para la próxima vez."
- SUBCASO C: Unidad "km" Y ninguna ciudad real (destino genérico como "hotel", "trabajo"):
  → actividad con quantity=null y clarifying_question="¿Cuántos km has recorrido en [medio de transporte]?"
- Otros casos (kg, kWh, litro, etc.) → actividad con quantity=null y clarifying_question:
  - Unidad "kg"    → "¿Cuántos gramos de [alimento] comiste? (p.ej. 200 para un filete normal)"
  - Unidad "kWh"   → "¿Cuántos kWh has consumido?"
  - Unidad "litro" → "¿Cuántos litros de [producto]?"
  - Unidad "hora"  → "¿Cuántas horas?"
  - Unidad "unidad"→ "¿Cuántas veces / unidades?"

DETECCIÓN DE CIUDAD DE ORIGEN: Si el usuario declara su ciudad de origen habitual
(ej: "vivo en Madrid", "mi ciudad es Sevilla", "salgo siempre desde Valencia", "soy de Bilbao"),
incluye el campo "home_city" en el objeto raíz de la respuesta.

RESPONDE ÚNICAMENTE CON UN OBJETO JSON VÁLIDO:

CASO NORMAL - Una o más actividades identificadas:
{{
  "type": "activity",
  "home_city": "<ciudad si el usuario la declara como habitual, si no omitir>",
  "activities": [
    {{
      "category": "<categoría>",
      "quantity": <número en unidad del factor, o null si falta>,
      "unit": "<unidad del factor>",
      "description": "<descripción breve>",
      "origin": "<ciudad origen si hay dos ciudades, null si solo hay destino, omitir si no aplica>",
      "destination": "<ciudad destino si aplica, si no omitir>",
      "clarifying_question": "<pregunta si quantity es null y no se pueden calcular km, si no omitir>"
    }}
  ]
}}

CASO Sin CO₂ pero declara ciudad de origen:
{{
  "type": "none",
  "home_city": "<ciudad declarada>"
}}

CASO Sin CO₂ y sin ciudad:
{{
  "type": "none"
}}"""

        user = f"Texto del usuario: {raw_text}"

        raw = self._chat(system, user, temperature=0.1)

        # Limpiar posibles bloques markdown si el modelo los añade
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            result = json.loads(raw)

            if isinstance(result, dict):
                activities: list[dict] = []

                if result.get("type") == "activity":
                    activities = result.get("activities", [])
                elif result.get("type") == "none":
                    activities = []
                else:
                    log.warning("Formato inesperado del LLM: %s", raw[:200])
                    return []

                # Propagar home_city como marcador al final si fue declarada
                if result.get("home_city"):
                    activities = list(activities) + [{"set_home_city": result["home_city"]}]

                return activities

            # Fallback si devuelve un array
            if isinstance(result, list):
                return result

            log.warning("Formato inesperado del LLM: %s", raw[:200])
            return []
        except json.JSONDecodeError:
            log.error("Error parseando JSON del LLM: %s", raw[:300])
            return []

    # ── Mejoras ──────────────────────────────────────────────────────────────

    def generate_improvements(
        self,
        total_kg: float,
        budget_kg: float,
        by_category: list[dict],
        by_factor: list[dict],
        period_days: int,
    ) -> list[dict]:
        """
        Genera sugerencias de mejora estructuradas basadas en el consumo real del usuario.

        Devuelve lista de dicts:
          [{category, action, tip, potential_saving_pct}]
        """
        cats_text = "\n".join(
            f"  - {c['category']}: {c['kg']:.3f} kg CO₂e ({c['pct']:.1f}% del total)"
            for c in by_category
        )
        factors_text = "\n".join(
            f"  - {f['name']}: {f['kg']:.3f} kg CO₂e"
            for f in by_factor
        )

        system = """Eres un experto en sostenibilidad ambiental.
Analiza el consumo de CO₂ del usuario y genera sugerencias de mejora concretas y accionables.

REGLA CRÍTICA: Solo puedes sugerir reducir o sustituir productos/actividades que el usuario
haya consumido realmente (los que aparecen en "Detalle de consumo"). No inventes consumos.

RESPONDE ÚNICAMENTE con un array JSON válido. Sin texto adicional. Sin bloques markdown.

Formato exacto:
[
  {
    "category": "<nombre de la categoría amplia>",
    "action": "<acción concreta en 1 frase referida a lo que el usuario realmente consumió>",
    "tip": "<consejo práctico adicional en 1-2 frases>",
    "potential_saving_pct": <número entero 5-60>
  }
]

Reglas:
- Genera entre 2 y 4 sugerencias, priorizando los factores con mayor impacto.
- Las acciones deben ser específicas: menciona el producto/actividad real consumido.
- potential_saving_pct es el % de reducción realista para esa categoría.
- Responde siempre en español."""

        user = f"""El usuario ha emitido {total_kg:.2f} kg CO₂e en los últimos {period_days} días.
Presupuesto sostenible para ese período: {budget_kg:.0f} kg.
{'Está dentro del presupuesto.' if total_kg <= budget_kg else f'Supera el presupuesto en {total_kg - budget_kg:.1f} kg.'}

Resumen por categoría (de mayor a menor impacto):
{cats_text}

Detalle de consumo (productos y actividades reales del usuario):
{factors_text}

Genera sugerencias basadas ÚNICAMENTE en lo que el usuario realmente ha consumido."""

        raw = self._chat(system, user, temperature=0.4)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
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