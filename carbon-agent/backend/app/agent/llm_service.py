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
import re
from datetime import date, timedelta

from openai import OpenAI

# Topings/condimentos que siempre generan una actividad separada.
# Aplica tanto a "X con TOPPING" como "X de TOPPING".
_TOPPINGS = [
    'mermelada', 'mantequilla', 'nocilla', 'nutella', 'miel',
    'nata', 'crema de cacahuete', 'tomate frito', 'aceite de oliva',
    'leche', 'queso', 'jamón', 'jamón york', 'atún',
]
_TOPPING_RE = re.compile(
    r'\b(?:con|de)\s+(' + '|'.join(re.escape(t) for t in _TOPPINGS) + r')\b',
    re.IGNORECASE,
)

from app.core.config import settings

log = logging.getLogger(__name__)


class LLMService:
    """Cliente OpenAI con métodos específicos para cada caso de uso del agente."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _yesterday(today_iso: str) -> str:
        try:
            return (date.fromisoformat(today_iso) - timedelta(days=1)).isoformat()
        except ValueError:
            return "desconocida"

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

    def _expand_compound_foods(self, text: str) -> str:
        """
        Pre-procesado: separa ingredientes de expresiones compuestas tipo
        'X con Y' y 'X de Y' para que el extractor principal los vea como ítems distintos.
        """
        system = """Eres un analizador de texto culinario. Tu única tarea es reescribir el texto separando los componentes de bebidas y alimentos compuestos.

REGLAS:
- "X con Y" entre alimentos/bebidas → escribe "X, Y"
- "X de Y" donde Y es un TOPPING o RELLENO comestible (mermelada, mantequilla, nocilla, miel, queso, jamón, atún, tomate, aceite) → escribe "X, Y"
- "X de Y" donde Y es SABOR o TIPO (naranja, limón, fresa, chocolate, vaca, soja, avena) → NO separar, dejar igual
- NO cambies nada más: cantidades, verbos, transportes, contexto.
- Si no hay compuestos alimentarios, devuelve el texto EXACTAMENTE igual.

EJEMPLOS:
"café con leche" → "café, leche"
"tostadas de mermelada" → "tostadas, mermelada"  ← mermelada es topping
"tostadas con mantequilla" → "tostadas, mantequilla"
"zumo de naranja" → "zumo de naranja"  ← naranja es sabor, NO separar
"leche de vaca" → "leche de vaca"  ← vaca es tipo, NO separar
"cola cao con leche" → "cola cao, leche"
"pan con mantequilla y mermelada" → "pan, mantequilla, mermelada"
"he desayunado café con leche y tostadas de mermelada" → "he desayunado café, leche y tostadas, mermelada"
"dos tostadas con mermelada" → "dos tostadas, mermelada"
"fui en coche con mi amigo" → "fui en coche con mi amigo"
"agua con gas" → "agua con gas"

Devuelve SOLO el texto reescrito, sin explicaciones ni comillas."""

        result = self._chat(system, text, temperature=0.0)
        expanded = result.strip()
        if expanded:
            log.debug("Expanded compound foods: %r → %r", text, expanded)
            return expanded
        return text

    def extract_activities(
        self,
        raw_text: str,
        factors_info: list[dict],
        pending_activity: dict | None = None,
        today: str | None = None,
        home_city: str | None = None,
        work_place: str | None = None,
    ) -> list[dict]:
        """
        Convierte texto libre en una lista de actividades estructuradas.

        Devuelve una lista de dicts con el esquema:
            [{"category": str, "quantity": float, "unit": str, "description": str}]

        El LLM solo identifica categoría y cantidad.
        El cálculo de emisiones se hace fuera de este servicio.
        """
        log.info("LLM extract input: %r", raw_text)

        categories_str = "\n".join(
            f"  - {f['category']}  →  {f['display_name']}  [unidad: {f['unit']}]"
            for f in factors_info
        )

        today_str = today or "desconocida"

        known_locations = ""
        if home_city or work_place:
            lines = ["UBICACIONES CONOCIDAS DEL USUARIO (úsalas directamente como origen/destino):"]
            if home_city:
                lines.append(f'  - "mi casa", "casa", "mi domicilio", "de casa" → {home_city}')
            if work_place:
                lines.append(f'  - "el trabajo", "mi trabajo", "la oficina", "al trabajo" → {work_place}')
            lines.append("Cuando el usuario mencione estas palabras como origen o destino, sustituye directamente por la ubicación conocida.")
            known_locations = "\n".join(lines) + "\n\n"

        system = f"""Eres un extractor de actividades con huella de carbono.
Tu tarea es analizar el texto del usuario e identificar TODAS las actividades
que tengan impacto en CO₂. Puede haber una o varias en el mismo mensaje.

════════════════════════════════════════════════════════
REGLA ABSOLUTA — ALIMENTOS ACOMPAÑANTES (aplica SIEMPRE, sin excepción):
Cuando el usuario menciona un alimento junto a otro con "con" o "de",
ambos son actividades INDEPENDIENTES aunque formen una expresión habitual en español.
NUNCA fusiones dos alimentos en una sola actividad.

CASOS CON "con" — SIEMPRE dos actividades:
  · "café con leche"         → [cafe] + [lacteos_leche]
  · "pan con mantequilla"    → [cereales] + [unknown:mantequilla]
  · "cola cao con leche"     → [cacao_o_unknown] + [lacteos_leche]
  · "yogur con miel"         → [lacteos_yogur] + [unknown:miel]
  · "tostada con mermelada"  → [cereales] + [mermelada]

CASOS CON "de" — depende:
  · Si Y es un ACOMPAÑAMIENTO/UNTABLE (mermelada, mantequilla, nocilla, miel, queso, jamón, atún, tomate) → DOS actividades:
      "tostada de mermelada"   → [cereales] + [mermelada]  ← OBLIGATORIO
      "pan de mantequilla"     → [cereales] + [unknown:mantequilla]
  · Si Y es un SABOR o TIPO (naranja, limón, fresa, vaca, avena, soja) → UNA actividad:
      "zumo de naranja"        → [zumo_naranja]  (no separar)
      "leche de avena"         → [leche_avena]   (no separar)

Si el segundo alimento no está en la lista de categorías, usa category="unknown".
════════════════════════════════════════════════════════

La fecha de hoy es: {today_str}

{known_locations}FECHA DE LA ACTIVIDAD (OBLIGATORIO COMPROBAR):
Si el usuario menciona que la actividad ocurrió en un momento distinto a hoy
(palabras como "ayer", "anteayer", "el lunes", "el martes pasado", "el 4 de abril", etc.)
debes incluir "activity_date" en el JSON raíz con la fecha ISO calculada.
Ejemplos usando hoy={today_str}:
  - "ayer comí..." → activity_date: "{self._yesterday(today_str)}"
  - "anteayer fui..." → activity_date: fecha de hace 2 días
  - Si no hay referencia a otra fecha → omite activity_date

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

   IMPORTANTE — alimentos con unidad "kg":
   - Si el usuario dice explícitamente gramos o kilos → quantity=ese valor, unit="g" o unit="kg".
     Ej: "150g de pollo" → quantity=150, unit="g"
   - Si el usuario dice un número de piezas/unidades (>1) → quantity=ese número, unit="unidades".
     NUNCA estimes el peso en kg. Solo devuelve el conteo.
     Ej: "cinco tostadas" → quantity=5, unit="unidades"   ← CORRECTO
     Ej: "cinco tostadas" → quantity=1.25, unit="kg"      ← INCORRECTO
     Ej: "tres huevos"   → quantity=3, unit="unidades"
     Ej: "dos cafés"     → quantity=2, unit="unidades"
   - Si no hay cantidad explícita ni número de piezas → quantity=null.
     Ej: "café con leche", "una tostada", "tostadas" → quantity=null

3. MÚLTIPLES ACTIVIDADES: El usuario puede mencionar varias acciones en un mismo mensaje.
   Identifica TODAS y devuélvelas en el array "activities", cada una con su propio estado.

POR CADA ACTIVIDAD IDENTIFICADA sigue esta lógica:

REGLA FUNDAMENTAL — LA LISTA ES LA VERDAD:
Todas las categorías de la lista tienen huella de carbono real y validada.
Si la actividad del usuario coincide semánticamente con el display_name de una categoría,
DEBES incluirla aunque personalmente creas que su impacto es pequeño o que no es "una actividad CO₂ típica".
Ejemplos: agua embotellada, streaming, caminar — todo lo que está en la lista tiene impacto medido.
NUNCA omitas una actividad porque creas que su CO₂ es bajo o irrelevante.

PASO 1: ¿Se puede asociar SEMÁNTICAMENTE a alguna categoría de la lista?
Cada categoría tiene un display_name con sinónimos y términos equivalentes que te sirven de guía.
Usa el display_name para hacer el mapeo semántico — no necesitas coincidencia literal, basta con que el término del usuario sea semánticamente equivalente.

Para vuelos aplica esta lógica obligatoria:
- avion_domestico: vuelo dentro del mismo país (ej: Madrid→Barcelona)
- avion_internacional: vuelo entre países distintos (ej: Madrid→Londres)

Si SÍ hay categoría identificada → Ir al PASO 2
Si NO hay categoría claramente relacionada → Ir al PASO 1B

PASO 1B: Término sin categoría exacta
REGLA DE ORO: siempre es mejor usar la categoría más cercana que devolver "unknown" o type="none".
- Si el término del usuario coincide PARCIALMENTE con el display_name de una categoría, USA ESA CATEGORÍA.
  Los calificativos de presentación (en conserva, fresco, enlatado, crudo, cocido…) NO cambian el cálculo CO₂ de forma significativa.
  Ejemplos:
    · usuario dice "espárragos blancos" → lista tiene "Espárragos blancos en conserva" → usa esa categoría ✓
    · usuario dice "salmón" → lista tiene "Salmón (de piscifactoría)" → usa esa categoría ✓
    · usuario dice "pan integral" → lista tiene "Pan (barra, integral)" → usa esa categoría ✓
- Solo usa category="unknown" si NINGUNA categoría de la lista se parece remotamente al término del usuario.
- Si no tiene huella de carbono en absoluto → omítela (no la incluyas)

PRE-PROCESADO OBLIGATORIO — DESCOMPOSICIÓN DE INGREDIENTES:
ANTES de mapear categorías, identifica TODOS los componentes del mensaje siguiendo estas reglas:

REGLA 1 — "X con Y" y "X de Y" (entre alimentos) SIEMPRE son actividades separadas:
Las partículas "con" y "de" entre alimentos/bebidas indican ingredientes distintos que deben registrarse por separado.
NUNCA colapses "X con Y" ni "X de Y" en un único ítem. Aplica esto aunque haya multiplicadores.

CASOS OBLIGATORIOS (memoriza estos exactos):
  · "café con leche"         → cafe(café) quantity=null  +  lacteos_leche(leche) quantity=null   ← AMBOS, nunca solo café
  · "cola cao con leche"     → cacao(cola cao) quantity=null  +  lacteos_leche(leche) quantity=null
  · "tostadas con mermelada" → cereales(tostadas) quantity=null  +  unknown(mermelada) quantity=null
  · "tostadas de mermelada"  → cereales(tostadas) quantity=null  +  unknown(mermelada) quantity=null
  · "pan con mantequilla"    → cereales(pan) quantity=null  +  unknown(mantequilla) quantity=null
  · "zumo con hielo"         → solo zumo (el hielo no tiene huella de carbono)
  · "dos tostadas con mermelada" → cereales quantity=2 unit="unidades"  +  unknown(mermelada) quantity=2 unit="unidades"
  · "tres cafés con leche"       → cafe quantity=3 unit="unidades"  +  lacteos_leche quantity=3 unit="unidades"

REGLA 2 — PRIORIDAD ABSOLUTA para factores específicos:
Si el ítem coincide con un factor EXACTO de la lista (por display_name o category), usa ESE factor directamente. NO lo descompongas.
Ejemplos:
  · "yogur de soja" → existe factor "yogur_de_soja" → usa esa categoría directamente ✓
  · "leche de avena" → existe factor "leche_avena" → usa esa categoría directamente ✓
  · "leche de soja"  → existe factor "leche_soja" → usa esa categoría directamente ✓

REGLA 3 — CONTENEDORES DE COMIDA (siempre descomponer):
  · "bocadillo de X" → cereales(pan) quantity=null + <factor del relleno X> quantity=null
  · "sandwich de X" → igual que bocadillo
  · "wrap de X" → igual que bocadillo
  · "pizza de X" → cereales(masa) quantity=null + <factor del relleno>
  · "taco de X" → cereales(tortilla) quantity=null + <factor del relleno>

REGLA 4 — PLATOS COMPUESTOS sin factor exacto:
Descompón en los 2-3 ingredientes con mayor impacto de CO₂:
  · "tortilla de patatas" → huevos(quantity=null) + patata(quantity=null)
  · "paella de marisco" → arroz(quantity=null) + marisco(quantity=null)
  · "pasta boloñesa" → cereales/pasta(quantity=null) + carne_vacuno(quantity=null)

REGLA 5 — MULTIPLICADORES con descomposición:
Si hay un número explícito delante de un plato/ítem compuesto, aplica ese quantity a TODOS sus ingredientes:
  · "dos tortillas de patatas" → huevos quantity=2 unit="unidades" + patata quantity=2 unit="unidades"
  · "dos tostadas con mermelada" → cereales quantity=2 unit="unidades" + mermelada quantity=2 unit="unidades"
  · "tres cafés con leche" → cafe quantity=3 unit="unidades" + lacteos_leche quantity=3 unit="unidades"

REGLA GENERAL de quantity en ingredientes descompuestos:
- Si NO hay cantidad explícita → quantity=null (el sistema aplica la porción estándar)
- Si hay número de piezas → quantity=N unit="unidades" en CADA ingrediente
- NUNCA estimes pesos en kg para ingredientes sin cantidad declarada

REGLA CRÍTICA — MENSAJES MIXTOS:
Si el mensaje contiene actividades identificables Y actividades desconocidas,
SIEMPRE extrae las identificables con su categoría correcta y marca solo las desconocidas como category="unknown".
NUNCA devuelvas type="none" si hay al menos una actividad identificable en el mensaje.

ITEMS DESCONOCIDOS (category="unknown"):
Cuando no puedas mapear un término a ninguna categoría conocida pero sospechas que tiene huella de carbono,
devuélvelo con:
  {{ "category": "unknown", "quantity": null, "unit": null, "description": "<término exacto del usuario>", "guessed_type": "<alimento|transporte|energia|compra|otro>" }}

CLASIFICACIÓN DE VUELOS (obligatorio):
- avion_domestico: vuelo DENTRO del mismo país (ej: Madrid→Barcelona, Sevilla→Bilbao)
- avion_internacional: vuelo ENTRE PAÍSES DISTINTOS (ej: Madrid→Londres, Barcelona→París)
- Si origin y destination son ciudades del mismo país → siempre avion_domestico
- Si no se sabe el destino aún → usa avion_domestico solo si el contexto indica vuelo nacional

PASO 2: ¿Hay un NÚMERO (o "un/una") con una unidad reconocida?
- Unidades reconocidas: números con g/kg/km/kWh/litros/ml/horas/unidades/vaso/vasos
- Si SÍ → actividad completa con quantity y unit convertidos a la unidad del factor
- Si NO → Ir al PASO 3

PASO 3: Categoría identificada pero falta cantidad.

DISTINCIÓN CLAVE — POI con nombre propio vs. lugar genérico:
  ✅ POI con nombre propio (geocodificable): "hotel Hesperia Madrid", "hotel Meliá Castilla", "restaurante El Bulli", "estadio Santiago Bernabéu"
  ❌ Lugar genérico (no geocodificable): "hotel" (solo esa palabra), "trabajo", "casa", "oficina", "gym"
  → Si el usuario dice "al hotel [nombre]" o "al restaurante [nombre]" → es un POI específico → SUBCASO A2
  → Si el usuario dice solo "al hotel" sin nombre → es genérico → SUBCASO C

- SUBCASO A: Unidad "km" Y el usuario menciona DOS ciudades/municipios (ej: "Madrid", "Barcelona"):
  → actividad con quantity=null, origin="<ciudad>", destination="<ciudad>"
- SUBCASO A2: Unidad "km" Y hay un POI con nombre propio Y se sabe la ciudad (en el mensaje o en el nombre del POI):
  → actividad con quantity=null, origin=null, destination="<nombre POI>, <ciudad>"
  → OBLIGATORIO: usar coma para separar POI y ciudad. Ejemplos:
    · "taxi al hotel Hesperia Madrid" → destination="Hotel Hesperia, Madrid"
    · "taxi al Hotel Meliá Castilla en Madrid" → destination="Hotel Meliá Castilla, Madrid"
    · "al estadio Santiago Bernabéu" (Madrid conocido del contexto) → destination="Estadio Santiago Bernabéu, Madrid"
- SUBCASO B: Unidad "km" Y solo UNA ciudad real mencionada:
  → actividad con quantity=null, origin=null, destination="<ciudad>", clarifying_question="¿Desde qué ciudad saliste? La recordaré para la próxima vez."
- SUBCASO C: Unidad "km" Y destino completamente genérico SIN nombre propio y SIN ciudad (ej: solo "el hotel", "el trabajo"):
  → actividad con quantity=null, needs_locations=true, clarifying_question="¿Desde qué lugar saliste y hasta dónde en [transporte]? (p.ej: 'desde la estación de Atocha hasta el hotel Meliá Castilla, Madrid')"
- Otros casos (kg, kWh, litro, etc.) → actividad con quantity=null y clarifying_question:
  - Unidad "kg"    → Si es alimento reconocido: "¿Cuántos gramos de [alimento] comiste? (p.ej. 200 para un filete normal)"
                   → Si es alimento DESCONOCIDO: "¿[alimento] es carne, pescado, verdura, fruta u otro? ¿Cuántos gramos más o menos?"
  - Unidad "kWh"   → "¿Cuántos kWh has consumido?"
  - Unidad "litro" → "¿Cuántos litros de [producto]?"
  - Unidad "hora"  → "¿Cuántas horas?"
  - Unidad "unidad"→ "¿Cuántas veces / unidades?"

DETECCIÓN DE CIUDAD DE ORIGEN: Si el usuario declara su ciudad de origen habitual
(ej: "vivo en Madrid", "mi ciudad es Sevilla", "salgo siempre desde Valencia", "soy de Bilbao"),
incluye el campo "home_city" en el objeto raíz de la respuesta.

VERIFICACIÓN FINAL OBLIGATORIA — antes de escribir el JSON, comprueba:
1. ¿El mensaje contiene "con" o "de" entre alimentos? → cada componente debe ser una actividad separada.
2. ¿Has incluido TODOS los ingredientes de cada expresión compuesta?
   - "café con leche" → ¿está café Y leche en activities?
   - "tostadas de/con mermelada" → ¿están tostadas Y mermelada en activities?
   - "cola cao con leche" → ¿están cola cao Y leche?
3. Si falta algún componente, añádelo antes de responder.

RESPONDE ÚNICAMENTE CON UN OBJETO JSON VÁLIDO:

CASO NORMAL - Una o más actividades identificadas:
{{
  "type": "activity",
  "home_city": "<ciudad si el usuario la declara como habitual, si no omitir>",
  "activity_date": "<YYYY-MM-DD si la actividad no fue hoy, si no omitir>",
  "activities": [
    {{
      "category": "<categoría>",
      "quantity": <número en unidad del factor, o null si falta>,
      "unit": "<unidad del factor>",
      "description": "<descripción breve>",
      "origin": "<ciudad origen si hay dos ciudades, null si solo hay destino, omitir si no aplica>",
      "destination": "<ciudad destino si aplica, si no omitir>",
      "clarifying_question": "<pregunta si quantity es null y no se pueden calcular km, si no omitir>",
      "needs_locations": "<true si es SUBCASO C — transporte con destino genérico que necesita origen y destino concretos; si no, omitir>"
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

        # Si hay una actividad pendiente de resolución, añadir contexto al prompt
        pending_section = ""
        if pending_activity:
            category = pending_activity.get("category", "?")
            description = pending_activity.get("description", "una actividad")
            question = pending_activity.get("question", "")
            known_destination = pending_activity.get("destination", "")
            destination_hint = (
                f" El destino ya es conocido: \"{known_destination}\"."
                if known_destination else ""
            )
            destination_instruction = (
                f"\n- OBLIGATORIO: usa EXACTAMENTE \"{known_destination}\" como destination en tu respuesta JSON."
                f" El origin será el lugar que mencione el usuario en este mensaje."
                if known_destination else ""
            )
            # Determine what unit a bare number implies based on what the question asked for
            question_lower = question.lower()
            if "gramo" in question_lower:
                implied_unit_hint = 'Si el usuario responde SOLO con un número sin unidad (ej: "200"), trátalo como GRAMOS → devuelve quantity=<número>, unit="g".'
            elif "litro" in question_lower or "ml" in question_lower:
                implied_unit_hint = 'Si el usuario responde SOLO con un número sin unidad, trátalo como LITROS → devuelve quantity=<número>, unit="litro".'
            elif "km" in question_lower or "kilómetro" in question_lower:
                implied_unit_hint = 'Si el usuario responde SOLO con un número sin unidad, trátalo como KM → devuelve quantity=<número>, unit="km".'
            elif "kwh" in question_lower:
                implied_unit_hint = 'Si el usuario responde SOLO con un número sin unidad, trátalo como kWh → devuelve quantity=<número>, unit="kWh".'
            elif "hora" in question_lower:
                implied_unit_hint = 'Si el usuario responde SOLO con un número sin unidad, trátalo como HORAS → devuelve quantity=<número>, unit="hora".'
            else:
                implied_unit_hint = f'Si el usuario responde SOLO con un número sin unidad, úsalo directamente como quantity=<número>.'

            pending_section = (
                f"\n\nCONTEXTO — ACTIVIDAD PENDIENTE DE INFORMACIÓN:\n"
                f"En el turno anterior el usuario mencionó \"{description}\" (categoría: {category})"
                f" pero faltaba información. Se le hizo esta pregunta: \"{question}\"{destination_hint}\n"
                f"\nDECIDE PRIMERO si el mensaje actual es una respuesta a la pregunta pendiente o una NUEVA actividad:\n"
                f"- Si el mensaje es solo una cantidad/número/lugar directamente relacionado con la pregunta → aplica el contexto pendiente.\n"
                f"- Si el mensaje describe claramente una ACTIVIDAD NUEVA diferente (p.ej. comida, otro viaje, energía) → ignora el contexto pendiente y procesa la nueva actividad normalmente. En ese caso incluye 'clear_pending: true' en el JSON raíz.\n"
                f"Ejemplos de RESPUESTA PENDIENTE: '15', '200 gramos', 'desde Atocha', '5 km', 'unos 10 km'\n"
                f"Ejemplos de NUEVA ACTIVIDAD: 'me comí una tortilla', 'fui al gym', 'encendí la calefacción'\n"
                f"\nSi ES respuesta pendiente:\n"
                f"- {implied_unit_hint}\n"
                f"- Si el usuario especifica la unidad explícitamente (ej: '200 gramos', '0.5 kg', '5 km') → úsala tal cual.\n"
                f"- Si el usuario repite el nombre sin cantidad → devuelve quantity=null y la clarifying_question original.\n"
                f"- Devuelve una actividad de categoría \"{category}\"."
                f"{destination_instruction}"
            )

        user = f"Texto del usuario: {raw_text}\n{pending_section}" if pending_section else f"Texto del usuario: {raw_text}"

        raw = self._chat(system, user, temperature=0.1)
        log.info("LLM extract raw: %s", raw[:400])

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

                # Propagar activity_date si el usuario mencionó una fecha pasada
                if result.get("activity_date"):
                    log.info("activity_date detectada por LLM: %s", result["activity_date"])
                    activities = list(activities) + [{"set_activity_date": result["activity_date"]}]
                else:
                    log.info("activity_date NO detectada (campo ausente o null en respuesta LLM)")

                # Si el LLM indica que la actividad pendiente debe limpiarse (nueva actividad distinta)
                if result.get("clear_pending"):
                    log.info("LLM señaló clear_pending=true: limpiando actividad pendiente")
                    activities = list(activities) + [{"clear_pending": True}]

                return activities

            # Fallback si devuelve un array
            if isinstance(result, list):
                return result

            log.warning("Formato inesperado del LLM: %s", raw[:200])
            return []
        except json.JSONDecodeError:
            log.error("Error parseando JSON del LLM: %s", raw[:300])
            return []

    def identify_unknown_items(self, raw_text: str) -> list[dict]:
        """
        Fallback: called when main extraction returns nothing.
        Asks the LLM to identify any words that sound like food, transport, or
        energy activities — even if it has no CO₂ data for them.
        Returns list of {term, guessed_type} dicts, or [] if nothing found.
        """
        system = """Eres un detector de términos con posible huella de carbono.
Se te dará un texto de usuario. Tu tarea es identificar palabras o frases que suenen a:
- alimento o bebida (plato, ingrediente, producto de supermercado, bebida embotellada…)
- medio de transporte o desplazamiento
- consumo de energía o electrodoméstico
- compra de producto de consumo

IMPORTANTE: Incluye cualquier término que suene a alimento, bebida, transporte o consumo,
incluso si su impacto CO₂ parece pequeño (ej: agua embotellada, fruta, zumo, botella de agua).
No incluyas verbos, adverbios ni palabras genéricas ("he", "comido", "y", etc.).

RESPONDE ÚNICAMENTE con un array JSON. Sin texto extra. Sin markdown.
Formato:
[{{"term": "<palabra exacta>", "guessed_type": "<alimento|transporte|energia|compra|otro>"}}]

Si no hay ningún término relevante, devuelve: []"""

        raw = self._chat(system, f"Texto: {raw_text}", temperature=0.1)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
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
          [{category, action, tip, first_step, potential_saving_pct, saving_kg}]
        """
        cats_text = "\n".join(
            f"  - {c['category']}: {c['kg']:.3f} kg CO₂e ({c['pct']:.1f}% del total)"
            for c in by_category
        )
        def fmt_qty(f: dict) -> str:
            qty = f.get("qty", 0)
            unit = f.get("unit", "")
            if unit == "kg" and qty < 1:
                return f"{round(qty * 1000)} g"
            if unit == "litro" and qty < 1:
                return f"{round(qty * 1000)} ml"
            return f"{qty:.0f} {unit}"

        factors_text = "\n".join(
            f"  - {f['name']}: {fmt_qty(f)} consumidos → {f['kg']:.3f} kg CO₂e"
            for f in by_factor
        )

        system = """Eres un experto en sostenibilidad ambiental. Analiza el consumo REAL del usuario y genera sugerencias MUY ESPECÍFICAS con pasos concretos.

REGLA CRÍTICA: Solo puedes mencionar productos que aparezcan en "Detalle de consumo". No inventes consumos.

Cada sugerencia DEBE cumplir TODOS estos requisitos:
1. "action": menciona el PRODUCTO EXACTO y la cantidad que ha consumido el usuario, luego propone un objetivo CONCRETO con cifra (ej: "Has consumido 800 g de ternera → reduce a 400 g")
2. "tip": un dato de contexto útil y específico al producto (ej: "La ternera genera 27 kg CO₂/kg, 5× más que el pollo")
3. "first_step": UN solo paso pequeño y realizable esta semana (ej: "Esta semana, sustituye una de tus raciones de ternera por pollo o legumbres")
4. "potential_saving_pct": % de reducción REALISTA para esa categoría (5-60)
5. "saving_kg": kg CO₂e que se ahorrarían aplicando la reducción propuesta (número decimal)

RESPONDE ÚNICAMENTE con un array JSON válido. Sin texto adicional. Sin bloques markdown.

[
  {
    "category": "<categoría>",
    "action": "<producto exacto + cantidad actual + objetivo concreto con cifra>",
    "tip": "<dato específico del impacto del producto, no consejo genérico>",
    "first_step": "<una sola acción pequeña y concreta para esta semana>",
    "potential_saving_pct": <5-60>,
    "saving_kg": <número decimal>
  }
]

- Genera entre 2 y 4 sugerencias, priorizando los factores con MAYOR impacto absoluto en kg CO₂e.
- Responde siempre en español."""

        user = f"""El usuario ha emitido {total_kg:.2f} kg CO₂e en los últimos {period_days} días.
Presupuesto sostenible para ese período: {budget_kg:.0f} kg.
{'Está dentro del presupuesto.' if total_kg <= budget_kg else f'Supera el presupuesto en {total_kg - budget_kg:.1f} kg.'}

Resumen por categoría (de mayor a menor impacto):
{cats_text}

Detalle de consumo con cantidades reales del usuario:
{factors_text}

Genera sugerencias basadas ÚNICAMENTE en los productos y cantidades listados arriba."""

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