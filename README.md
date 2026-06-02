# Carbon Agent — TFM UNIR

> **Agente conversacional de huella de carbono personal.**
> El usuario describe sus actividades en lenguaje natural y el agente estima las emisiones de CO₂ de forma determinista, ofrece recomendaciones personalizadas y recuerda sus hábitos entre sesiones.

---

## ✨ Funcionalidades principales

| Área | Detalle |
|---|---|
| **Chat natural** | Registra actividades como "he conducido 20 km" o "comí 300 g de ternera" |
| **Cálculo CO₂ determinista** | Siempre `cantidad × factor` — el LLM **nunca** calcula emisiones |
| **Distancias automáticas** | Geocodificación con OpenStreetMap para resolver trayectos origen → destino |
| **Preguntas aclaratorias** | Si falta información (origen, cantidad), el agente la pide antes de calcular |
| **Memoria de usuario** | Guarda ciudad de origen, lugar de trabajo y transporte habitual |
| **Dashboard con anillos SVG** | Vista de emisiones por período (día / semana / mes) con indicador visual de presupuesto |
| **Historial editable** | Edita texto y fecha de actividades pasadas; las emisiones se recalculan automáticamente |
| **Panel de mejoras** | Sugerencias de reducción personalizadas generadas por el LLM basadas en consumo real |
| **Resumen de período** | Totales agregados, gráfico por categorías y comparativa vs. objetivo anual |
| **Perfil de usuario** | Ciudad de origen, lugar de trabajo y nombre para personalizar el agente |

---

## 🏗️ Arquitectura general

```
carbon-agent/
├── backend/                    # API REST + Agente IA
│   ├── app/
│   │   ├── agent/              # Componentes del agente (ver sección dedicada)
│   │   ├── api/                # Endpoints FastAPI
│   │   ├── core/               # Configuración
│   │   ├── db/                 # Base de datos + seed
│   │   ├── models/             # ORM SQLAlchemy
│   │   └── schemas/            # Schemas Pydantic
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
├── frontend/                   # SPA React + TypeScript
│   └── src/
│       ├── components/         # Componentes UI (ver sección dedicada)
│       ├── hooks/              # Lógica de estado y API
│       ├── services/           # Cliente HTTP
│       └── types/              # Tipos TypeScript
└── docs/
```

---

## 🤖 Agentes y servicios del backend

El backend está organizado en cinco módulos especializados dentro de `app/agent/`. Cada uno tiene una responsabilidad única y bien delimitada.

---

### 🎯 `orchestrator.py` — CarbonAgent

**Coordina todo el pipeline** de procesamiento de una actividad de principio a fin.

```
texto del usuario
      │
      ├─► [MemoryService]      ← carga home_city, work_place, actividad pendiente
      │
      ├─► [Extractor]          ← texto → actividades estructuradas (usa LLM)
      │         │
      │         ├── marcadores: set_home_city, set_pending_activity, clarifying_question
      │         └── ExtractedActivity[] validadas
      │
      ├─► [CO2Calculator]      ← cálculo determinista: cantidad × factor
      │
      ├─► [MemoryService]      ← actualiza hábitos tras cada actividad
      │
      └─► [LLMService]         ← genera recomendación personalizada (texto)
```

**Casos que gestiona:**
- Actividad completa → calcula y recomienda
- Falta información → devuelve pregunta aclaratoria (`is_question: true`)
- Solo se declara ciudad de origen → confirma y memoriza
- Nada identificado → mensaje de ayuda al usuario
- Actividad pendiente resuelta en turno siguiente → completa el cálculo

---

### 🔍 `extractor.py` — Extractor

**Convierte texto libre en actividades estructuradas** consultando el LLM con las categorías válidas de la base de datos.

**Responsabilidades:**
1. Carga todas las categorías válidas desde `emission_factors` en BD
2. Llama a `LLMService.extract_activities()` con esas categorías como contexto
3. Valida cada actividad: categoría existe en BD, cantidad positiva
4. Resuelve el objeto `EmissionFactor` correspondiente
5. Gestiona **conversión de unidades** automática: g→kg, ml→litro, vasos→litros
6. Detecta actividades de **transporte sin cantidad** y lanza geocodificación
7. Gestiona **marcadores especiales**: `set_home_city`, `set_pending_activity`, `clarifying_question`

**Lógica de transporte (subcasos):**

| Situación | Acción |
|---|---|
| Origen + destino explícitos (dos ciudades) | Geocodifica directamente |
| Solo destino + `home_city` en memoria | Usa `home_city` como origen |
| POI con nombre propio (ej: "Hotel Meliá Castilla") | Geocodifica POI + ciudad |
| Destino genérico ("el trabajo", "el hotel") | Pregunta al usuario |
| Sin `home_city` y sin origen | Pregunta y memoriza ciudad |

---

### 🧮 `calculator.py` — CO2Calculator

**Cálculo 100% determinista** de emisiones de CO₂. No realiza ninguna llamada externa ni al LLM.

```python
# Única fórmula usada
amount_kg_co2e = quantity × factor.factor_kg_co2e
```

Recibe una lista de `ExtractedActivity` (con el `EmissionFactor` ya resuelto) y persiste los objetos `Emission` en la sesión SQLAlchemy. El commit lo hace el orquestador.

---

### 🧠 `llm_service.py` — LLMService

**Wrapper sobre la API de OpenAI** con tres métodos específicos. Nunca recibe factores de emisión ni hace cálculos numéricos.

| Método | Propósito | Temperatura |
|---|---|---|
| `extract_activities()` | Convierte texto → lista de actividades estructuradas (JSON) | 0.1 |
| `generate_recommendation()` | Genera recomendación personalizada tras un registro | 0.7 |
| `generate_improvements()` | Genera sugerencias de reducción basadas en consumo real | 0.4 |

**Prompt de extracción** incluye:
- Lista completa de categorías válidas con su unidad (`kg`, `km`, `kWh`, `litro`, etc.)
- Reglas de conversión de unidades
- Subcasos para transporte (A, A2, B, C)
- Detección de ciudad de origen habitual
- Contexto de actividad pendiente del turno anterior (multi-turno)
- Distinción vuelo doméstico vs. internacional

**Prompt de mejoras**: solo puede sugerir reducir lo que el usuario ha consumido realmente. No inventa consumos.

---

### 📍 `distance_service.py` — DistanceService

**Calcula distancias entre lugares** usando geocodificación gratuita, sin API key.

- **Geocodificador**: Nominatim (OpenStreetMap) vía `geopy`
- **Fórmula de distancia**: Haversine (distancia de gran círculo)
- **Caché en memoria**: `@lru_cache(maxsize=256)` para evitar llamadas repetidas
- **Rate limiting**: `time.sleep(1)` obligatorio por política de Nominatim (máx. 1 req/s)
- Devuelve `None` si alguna localización no se puede geocodificar

---

### 💾 `memory.py` — MemoryService

**Persiste y recupera el contexto del usuario** en la tabla `user_memory` (clave-valor por usuario).

| Clave | Contenido | Uso |
|---|---|---|
| `home_city` | Ciudad de origen habitual | Origen por defecto en trayectos de transporte |
| `work_place` | Lugar de trabajo / estudio | Referencia para trayectos al trabajo |
| `transporte_habitual` | Último medio de transporte usado | Contexto para recomendaciones |
| `pending_activity` | Actividad a medio completar (JSON) | Resolución multi-turno |

**Operaciones principales:**
- `get_memory()` / `update_memory()` — lectura y upsert genérico
- `get_home_city()` / `set_home_city()` — ciudad de origen
- `get_pending_activity()` / `set_pending_activity()` / `clear_pending_activity()` — gestión de actividades incompletas
- `infer_habits()` — detecta el transporte habitual del usuario a partir de sus registros

---

## 🖥️ Componentes del frontend

La interfaz está construida con React 18 + TypeScript. Los componentes son funcionales y se comunican con el backend a través de TanStack Query y Axios.

---

### 💬 `ChatBubble.tsx`

Renderiza los mensajes del chat diferenciando visualmente el mensaje del usuario y la respuesta del agente. Muestra:
- Texto de la respuesta del agente
- Total de emisiones calculadas (`X.XXX kg CO₂e`) si hay actividad
- Desglose por sub-actividad si el mensaje incluía varias
- Indicador especial cuando el agente hace una **pregunta aclaratoria**

---

### ⌨️ `ChatInput.tsx`

Campo de entrada del chat con:
- Envío con `Enter` (y salto de línea con `Shift+Enter`)
- Bloqueo del input mientras el agente procesa
- Indicador de carga / estado "Pensando…"

---

### 📊 `DailyDashboard.tsx`

Panel principal con **anillos SVG animados** que muestran el consumo vs. presupuesto.

**Modos de visualización:** Día · Semana · Mes (navegables con flechas `‹ ›`)

**Elementos:**
- **Anillo principal** — total del período en kg CO₂e vs. presupuesto proporcional; se pone rojo al superarlo
- **Anillos por categoría** — uno por cada categoría activa (Alimentación, Transporte, Energía, Residuos, Compras, Ocio) con su propio color
- **Lista de actividades** — detalle de cada actividad del período con código de color por impacto (verde < 1 kg · naranja < 5 kg · rojo ≥ 5 kg)

El presupuesto se calcula proporcionalmente desde el objetivo anual configurado en `SettingsPanel`.

---

### 📋 `HistoryPanel.tsx`

Lista completa del historial de actividades con:
- **Edición inline** — al pulsar el lápiz se despliega un formulario con textarea (texto) y datetime picker (fecha), y se reenvía al backend para recalcular
- **Eliminación individual** — botón de papelera por actividad
- **Borrar todo** — requiere doble confirmación para evitar borrados accidentales
- Código de color en el total de cada entrada (verde / naranja / rojo)
- Fecha y cantidades originales visibles bajo cada entrada

---

### 💡 `ImprovementsPanel.tsx`

Genera y muestra **sugerencias de reducción de huella** personalizadas:

- Llama al endpoint `/api/improvements` que a su vez invoca al LLM con el consumo real del usuario
- Muestra el contexto de presupuesto (dentro / superado) con color de alerta
- Agrupa sugerencias por categoría en **tarjetas** que incluyen:
  - Icono y nombre de categoría
  - Total de kg y % del total (con barra de progreso de color)
  - Acción concreta + consejo adicional
  - Badge con ahorro potencial estimado (`−X% · ahorra ~Y kg`)
- Botón "🔄 Regenerar sugerencias" para obtener nuevas ideas del LLM

---

### 📈 `SummaryPanel.tsx`

Panel de resumen con **dos vistas** seleccionables por pestañas:

**Vista general:**
- `BudgetCard` — total del período vs. presupuesto sostenible con barra de progreso tricolor
- Tarjetas de estadísticas: número de actividades y media por actividad
- Gráfico de barras (Recharts) con las top categorías por emisión

**Vista por categoría** (al hacer clic en una pestaña de categoría):
- Total de la categoría y número de actividades
- Gráfico de tarta (Recharts) con desglose por factor de emisión (ej: "Ternera", "Pollo", "Cerdo" dentro de "Alimentación")
- Lista detallada con kg por factor

---

### ⚙️ `SettingsPanel.tsx`

Panel de configuración con dos sub-pestañas:

**🎯 Objetivo CO₂:**
- Slider de 2 t a 8 t/año con botones de acceso rápido a niveles estándar
- Contexto climático para cada nivel: temperatura de calentamiento asociada y descripción del esfuerzo requerido (basado en Acuerdo de París e IPCC)
- Equivalencia automática: muestra el objetivo en kg/mes y kg/día
- Explicación didáctica de qué es la huella de carbono

**👤 Preferencias:**
- Nombre del usuario (para personalizar respuestas del agente)
- Ciudad de origen — se sincroniza con `home_city` en `MemoryService`
- Lugar de trabajo / estudios — usado para trayectos habituales
- Los cambios se persisten en la BD via `PATCH /api/profile`

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Frontend** | React 18 + TypeScript · Vite · TanStack Query · Recharts · Axios · date-fns |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic |
| **Agente IA** | OpenAI API (GPT-4o-mini por defecto) |
| **Geocodificación** | geopy 2.4 + Nominatim (OpenStreetMap) — sin API key |
| **Base de datos** | SQLite (MVP) → PostgreSQL (producción) |
| **Tests** | pytest + httpx + pytest-asyncio |

---

## 🚀 Inicio rápido

### Backend

```bash
cd carbon-agent/backend

# Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# → Edita .env y añade tu OPENAI_API_KEY

# Inicializar base de datos (crea tablas + seed de factores de emisión)
python -m app.db.init_db

# Arrancar el servidor
uvicorn main:app --reload
```

- API REST → `http://localhost:8000`
- Swagger UI → `http://localhost:8000/docs`

### Frontend

```bash
cd carbon-agent/frontend
npm install
npm run dev
```

- Interfaz → `http://localhost:5173`

---

## 📡 Endpoints REST

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/activity` | Registra una actividad en lenguaje natural |
| `GET` | `/api/history` | Historial de actividades del usuario |
| `PATCH` | `/api/history/{id}` | Edita texto/fecha y recalcula emisiones |
| `DELETE` | `/api/history/{id}` | Elimina una actividad concreta |
| `DELETE` | `/api/history` | Borra todo el historial del usuario |
| `GET` | `/api/summary` | Totales agregados + top categorías del período |
| `GET` | `/api/profile` | Perfil del usuario (ciudad, trabajo, nombre) |
| `PATCH` | `/api/profile` | Actualiza el perfil del usuario |
| `GET` | `/api/improvements` | Sugerencias de mejora generadas por el LLM |

---

## 🗄️ Modelo de datos

```
emission_factors   — factores estáticos de CO₂ por categoría (seed, nunca modificados en runtime)
activities         — registro de actividades del usuario (texto original + timestamp)
emissions          — resultado del cálculo: quantity × factor_kg_co2e  (nunca generado por LLM)
user_memory        — hábitos y preferencias del usuario (clave-valor por user_id)
```

---

## ⚙️ Variables de entorno

```env
OPENAI_API_KEY=sk-...                         # Requerida
OPENAI_MODEL=gpt-4o-mini                      # Modelo a usar (por defecto)
DATABASE_URL=sqlite:///./carbon_agent.db      # Default SQLite (MVP)
```

---

## 🧪 Tests

```bash
cd carbon-agent/backend
pytest tests/ -v
```

- `test_phase1.py` — unitarios: extracción, cálculo, memoria
- `test_phase2.py` — integración: endpoints API con cliente httpx

---

## 🏛️ Principio arquitectónico clave

> **El LLM nunca calcula emisiones.** Solo interpreta lenguaje natural y genera texto.
> Todo cálculo de CO₂ es **determinista**: `cantidad × factor_kg_co2e`.
>
> Esto garantiza **trazabilidad**, **reproducibilidad** y **confianza** en los resultados.

### Flujo completo de una actividad

```
Usuario: "conduje 30 km al trabajo"
         │
         ▼
  ┌─────────────┐
  │MemoryService│  ← carga home_city, work_place, pending_activity
  └──────┬──────┘
         │
         ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ Extractor + LLMService (extract_activities, temperature=0.1)   │
  │                                                                │
  │  Input:  "conduje 30 km al trabajo"                           │
  │  Output: { category: "coche_gasolina", quantity: 30, unit: "km" } │
  └──────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────┐
  │ CO2Calculator (sin LLM, 100% determinista)   │
  │                                              │
  │  30 km × 0.192 kg/km = 5.760 kg CO₂e        │
  └──────────────────────────┬───────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ LLMService (generate_recommendation, temperature=0.7)            │
  │                                                                  │
  │  Recibe: total=5.76 kg + resumen actividades + memoria usuario  │
  │  Genera: "Hoy has emitido 5.76 kg conduciendo. Considera..."    │
  └──────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
  ┌──────────────┐
  │  Frontend    │  ← muestra resultado, anillo del dashboard actualizado
  └──────────────┘
```
