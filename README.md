# Planet Pulse — TFM UNIR

> **Agente conversacional de huella de carbono personal.**
> El usuario describe sus actividades en lenguaje natural y el agente estima las emisiones de CO₂ de forma determinista, ofrece recomendaciones personalizadas y recuerda sus hábitos entre sesiones.

---

## ✨ Funcionalidades principales

| Área | Detalle |
|---|---|
| **Chat natural** | Registra actividades como "he conducido 20 km" o "comí 300 g de ternera" |
| **Cálculo CO₂ determinista** | Siempre `cantidad × factor` — el LLM **nunca** calcula emisiones |
| **Distancias automáticas** | Geocodificación con OpenStreetMap para resolver trayectos origen → destino |
| **Fechas en lenguaje natural** | Detecta "ayer", "el martes pasado", "el 4 de abril"… y registra la actividad con esa fecha |
| **Preguntas aclaratorias** | Si falta información (origen, cantidad), el agente la pide antes de calcular, incluso a lo largo de varios turnos |
| **Memoria de usuario** | Guarda ciudad de origen, lugar de trabajo, trayecto habitual (commute) y transporte más usado |
| **Autenticación** | Login con Auth0 (OAuth2/JWT); cada usuario solo ve sus propios datos |
| **Dashboard con anillos SVG** | Vista de emisiones por período (día / semana / mes) con indicador visual de presupuesto |
| **Historial editable** | Edita texto, fecha y cantidad de actividades pasadas; las emisiones se recalculan automáticamente |
| **Panel de mejoras** | Sugerencias de reducción personalizadas generadas por el LLM, con equivalencias cotidianas ("equivale a 36 min conduciendo") |
| **Resumen de período** | Totales agregados, gráfico por categorías y comparativa vs. objetivo anual |
| **Perfil y porciones** | Ciudad de origen, lugar de trabajo, nombre y raciones por defecto personalizables por el usuario |
| **Rutina diaria (recurrente)** | Actividades que se registran automáticamente una vez al día (electricidad, gas, TV, móvil…) |
| **Panel de administración** | Solo para usuarios con rol `admin`: revisión de términos desconocidos y CRUD completo de factores de emisión |

---

## 🏗️ Arquitectura general

```
carbon-agent/
├── backend/                    # API REST + Agente IA
│   ├── app/
│   │   ├── agent/              # Componentes del agente (ver sección dedicada)
│   │   ├── api/                # Endpoints FastAPI (activities.py)
│   │   ├── core/                # Configuración + autenticación Auth0
│   │   ├── db/                  # Base de datos + seed de factores
│   │   ├── models/               # ORM SQLAlchemy
│   │   └── schemas/              # Schemas Pydantic
│   ├── tests/
│   ├── main.py                  # Entry point FastAPI + CORS + healthcheck
│   ├── requirements.txt
│   └── railway.toml              # Despliegue backend en Railway
└── frontend/                   # SPA React + TypeScript
    ├── src/
    │   ├── components/          # Componentes UI (ver sección dedicada)
    │   ├── hooks/                # Lógica de estado y API (TanStack Query)
    │   ├── services/             # Cliente HTTP (Axios + interceptor Auth0)
    │   └── types/                # Tipos TypeScript
    └── railway.toml              # Despliegue frontend en Railway
```

---

## 🤖 Agentes y servicios del backend

El backend está organizado en siete módulos especializados dentro de `app/agent/`. Cada uno tiene una responsabilidad única y bien delimitada.

---

### 🎯 `orchestrator.py` — CarbonAgent

**Coordina todo el pipeline** de procesamiento de una actividad de principio a fin.

```
texto del usuario
      │
      ├─► detección de fecha (regex, en Python — "ayer", "el lunes pasado", "el 4 de abril"…)
      │
      ├─► [MemoryService]      ← carga home_city, work_place, commute_km, pending_activity, porciones
      │
      ├─► [Extractor]          ← texto → actividades estructuradas (usa LLM)
      │         │
      │         ├── marcadores: set_home_city, set_pending_activity, set_activity_date,
      │         │                clarifying_question, unknown_items, clear_pending
      │         └── ExtractedActivity[] validadas
      │
      ├─► [CO2Calculator]      ← cálculo determinista: cantidad × factor
      │
      ├─► [MemoryService]      ← actualiza hábitos y commute_km tras cada actividad
      │
      └─► [LLMService]         ← genera recomendación personalizada (texto)
```

**Casos que gestiona:**
- Actividad completa → calcula y recomienda
- Falta información → devuelve pregunta aclaratoria (`is_question: true`), incluso a través de varios turnos
- Solo se declara ciudad de origen → confirma y memoriza
- Nada identificado → mensaje de ayuda, o aviso si el término se registró como "desconocido" para revisión de admin
- Actividad pendiente resuelta en turno siguiente → completa el cálculo y, si era un trayecto habitual (commute), guarda los km para la próxima vez
- Actividad con fecha pasada ("ayer conduje 20 km") → se persiste con `created_at` sobrescrito

También expone `reprocess_activity()`, usado al editar una entrada del historial: vuelve a extraer y calcular sin duplicar la actividad.

---

### 🔍 `extractor.py` — Extractor

**Convierte texto libre en actividades estructuradas** consultando el LLM con las categorías válidas de la base de datos.

**Responsabilidades:**
1. Carga todas las categorías válidas desde `emission_factors` en BD
2. Llama a `LLMService.extract_activities()` con esas categorías, la memoria del usuario y sus porciones personalizadas como contexto
3. Valida cada actividad: categoría existe en BD, cantidad positiva
4. Resuelve el objeto `EmissionFactor` correspondiente
5. Gestiona **conversión de unidades** automática: g→kg, ml→litro, vasos→litros
6. Detecta actividades de **transporte sin cantidad** y lanza geocodificación
7. Gestiona **marcadores especiales**: `set_home_city`, `set_pending_activity`, `set_activity_date`, `clarifying_question`, `unknown_items`, `clear_pending`
8. Registra en `unknown_items` cualquier término que el usuario mencione y no exista en el catálogo, para revisión posterior desde el panel de admin

**Lógica de transporte (subcasos):**

| Situación | Acción |
|---|---|
| Origen + destino explícitos (dos ciudades) | Geocodifica directamente |
| Solo destino + `home_city` en memoria | Usa `home_city` como origen |
| Trayecto al trabajo/estudios + `work_place`/`commute_km` en memoria | Usa la distancia guardada del commute habitual |
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
- Lista completa de categorías válidas con su unidad (`kg`, `km`, `kWh`, `litro`, etc.) y porciones por defecto del usuario
- Reglas de conversión de unidades
- Subcasos para transporte (origen/destino, commute, POI, genérico)
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
- `is_geocodable()` — comprobación rápida usada por el endpoint `/api/geocode/check` para validar direcciones en Ajustes
- Devuelve `None` si alguna localización no se puede geocodificar

---

### 🌍 `equivalences.py` — Equivalencias cotidianas

**Traduce una cifra de kg CO₂e a algo tangible**, usando los mismos factores deterministas ya guardados en BD (nunca el LLM).

- Ejemplo: `X kg CO₂e` → "36 minutos conduciendo" (usando el factor de `coche_gasolina` y una velocidad media asumida de 50 km/h)
- Se usa en el panel de mejoras para dar contexto intuitivo a cada sugerencia de ahorro

---

### 💾 `memory.py` — MemoryService

**Persiste y recupera el contexto del usuario** en la tabla `user_memory` (clave-valor por usuario).

| Clave | Contenido | Uso |
|---|---|---|
| `home_city` | Ciudad de origen habitual | Origen por defecto en trayectos de transporte |
| `work_place` | Lugar de trabajo / estudio | Referencia para trayectos al trabajo |
| `commute_km` | Distancia del trayecto casa→trabajo | Evita repetir la geocodificación cada vez |
| `transporte_habitual` | Último medio de transporte usado | Contexto para recomendaciones |
| `pending_activity` | Actividad a medio completar (JSON) | Resolución multi-turno |
| `portion_<categoría>` | Ración personalizada por categoría | Sustituye la ración por defecto del catálogo |
| `recurring_<categoría>` | Configuración de rutina diaria (cantidad, activo) | Registro automático diario |
| `recurring_last_applied` | Fecha del último registro automático | Evita duplicar la rutina el mismo día |

**Operaciones principales:**
- `get_memory()` / `update_memory()` / `clear_keys()` — lectura, upsert y borrado genérico
- `get_home_city()` / `set_home_city()`, `get_work_place()`, `get_commute_km()` / `set_commute_km()`
- `get_pending_activity()` / `set_pending_activity()` / `clear_pending_activity()` — gestión de actividades incompletas
- `get_portions()` / `set_portions()` — raciones personalizadas
- `get_recurring()` / `set_recurring()` / `get_recurring_last_applied()` / `set_recurring_last_applied()` — rutina diaria
- `infer_habits()` — detecta el transporte habitual del usuario a partir de sus registros

---

## 🔐 Autenticación y autorización

- **Auth0** gestiona el login (OAuth2 + JWT) — el frontend usa `@auth0/auth0-react` para el flujo de redirección y obtener el access token
- El backend valida cada request con `app/core/auth.py`: descarga las claves públicas JWKS de Auth0, verifica la firma RS256, el `audience` y el `issuer`
- `get_current_user()` — dependencia FastAPI que extrae el `sub` del token como `user_id`; todos los endpoints filtran datos por este ID
- `get_admin_user()` — dependencia adicional que exige el rol `admin` en el claim personalizado `https://planet-pulse-api/roles`; protege todos los endpoints `/api/admin/*`
- En el frontend, `useIsAdmin()` lee ese mismo claim del perfil de Auth0 para mostrar u ocultar la pestaña "Admin"

---

## 🖥️ Componentes del frontend

La interfaz está construida con React 18 + TypeScript. Los componentes son funcionales y se comunican con el backend a través de TanStack Query y Axios.

---

### 🔑 `LoginPage.tsx`

Pantalla de bienvenida mostrada cuando el usuario no está autenticado. Un único botón lanza `loginWithRedirect()` de Auth0.

---

### 🛡️ `ErrorBoundary.tsx`

Captura errores de renderizado de React (necesita ser una clase, no un hook) para evitar una pantalla en blanco en producción. Muestra un mensaje de error y un botón para recargar.

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
  - **Equivalencia cotidiana** (ej: "equivale a 36 minutos conduciendo")
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

Panel de configuración con tres sub-pestañas:

**🎯 Objetivo CO₂:**
- Slider de 2 t a 8 t/año con botones de acceso rápido a niveles estándar
- Contexto climático para cada nivel: temperatura de calentamiento asociada y descripción del esfuerzo requerido (basado en Acuerdo de París e IPCC)
- Equivalencia automática: muestra el objetivo en kg/mes y kg/día
- Explicación didáctica de qué es la huella de carbono

**👤 Preferencias** (agrupa varios sub-paneles):
- **Perfil** — nombre del usuario, ciudad de origen y lugar de trabajo, con verificación en vivo de que la dirección es geocodificable (`/api/geocode/check`); se sincroniza con `home_city`/`work_place` en `MemoryService`
- **Rutina diaria** — activa/desactiva y ajusta la cantidad de actividades recurrentes (electricidad, gas, TV, móvil…) que se registran automáticamente una vez al día
- **Historial** — botón para borrar todo el historial (doble confirmación)
- **Cuenta** — datos de sesión y cierre de sesión (visible en móvil; en escritorio ya está en la barra lateral)
- Los cambios se persisten en la BD vía `PATCH /api/profile`, `PATCH /api/recurring`

**🍽️ Porciones:**
- Tabla de raciones por defecto para cada categoría no-transporte (ej. "pechuga de pollo: 150 g")
- El usuario puede sobrescribir cada ración; un botón "↺" restaura el valor de catálogo
- Estas porciones se usan cuando el usuario no especifica cantidad ("comí pollo" → usa la ración guardada)

---

### 🛠️ `AdminPanel.tsx`

Solo visible para usuarios con rol `admin` (`useIsAdmin()`). Dos secciones:

**Items desconocidos:**
- Lista de términos que el LLM no pudo mapear a ninguna categoría del catálogo, con su contexto original y una categoría principal sugerida
- Pestañas por estado: Pendiente · Añadido · Rechazado · Todos
- Selección múltiple y borrado en lote
- Al abrir un item: aceptar (crea un factor de emisión nuevo prellenado), rechazar o eliminar

**Factores de emisión:**
- Tabla completa de `emission_factors` con búsqueda y filtro por categoría principal
- Alta, edición y borrado de factores desde un formulario compartido (`FactorForm`), incluyendo fuente, año, tipo de fuente y notas para trazabilidad científica
- Al escribir el nombre visible, genera automáticamente el slug de categoría interna

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Frontend** | React 18 + TypeScript · Vite · TanStack Query · Recharts · Axios · date-fns · lucide-react · Bootstrap (utilidades) |
| **Autenticación** | Auth0 (`@auth0/auth0-react` en frontend · `python-jose` + JWKS en backend) |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic |
| **Agente IA** | OpenAI API (GPT-4o-mini por defecto) |
| **Geocodificación** | geopy 2.4 + Nominatim (OpenStreetMap) — sin API key |
| **Base de datos** | SQLite (MVP) → PostgreSQL (producción, vía `psycopg2-binary`) |
| **Tests** | pytest + httpx + pytest-asyncio |
| **Despliegue** | Railway (backend + frontend, `railway.toml` en ambos con Nixpacks) |

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
# → Edita .env y añade tu OPENAI_API_KEY y la configuración de Auth0

# Arrancar el servidor (init_db() se ejecuta automáticamente al arrancar)
uvicorn main:app --reload
```

- API REST → `http://localhost:8000`
- Swagger UI → `http://localhost:8000/docs`

### Frontend

```bash
cd carbon-agent/frontend
npm install
cp .env.example .env.local
# → Edita .env.local si tu backend no corre en el proxy de Vite por defecto
npm run dev
```

- Interfaz → `http://localhost:5173`

---

## 📡 Endpoints REST

Todos los endpoints (salvo `/health`) requieren un Bearer token de Auth0. Los prefijados con `/admin` exigen además el rol `admin`.

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/activity` | Registra una actividad en lenguaje natural |
| `GET` | `/api/history` | Historial de actividades del usuario (filtrable por rango de fechas) |
| `PATCH` | `/api/history/{id}` | Edita texto/fecha de una actividad y recalcula sus emisiones |
| `DELETE` | `/api/history/{id}` | Elimina una actividad concreta |
| `DELETE` | `/api/history` | Borra todo el historial del usuario |
| `PATCH` | `/api/emissions/{id}` | Edita la cantidad de una emisión concreta y recalcula su CO₂ |
| `GET` | `/api/summary` | Totales agregados + top categorías del período |
| `GET` | `/api/profile` | Perfil del usuario (ciudad, trabajo, nombre) |
| `PATCH` | `/api/profile` | Actualiza el perfil del usuario |
| `GET` | `/api/geocode/check` | Comprueba si una dirección es geocodificable |
| `GET` | `/api/portions` | Raciones por defecto por categoría, con overrides del usuario |
| `PATCH` | `/api/portions` | Guarda raciones personalizadas |
| `GET` | `/api/recurring` | Configuración de rutina diaria (actividades recurrentes) |
| `PATCH` | `/api/recurring` | Actualiza la rutina diaria |
| `POST` | `/api/recurring/apply` | Aplica la rutina diaria (una vez por día; se llama automáticamente al abrir la app) |
| `GET` | `/api/improvements` | Sugerencias de mejora generadas por el LLM, con equivalencias |
| `GET` | `/api/admin/unknown-items` | Lista items desconocidos por estado, para revisión de admin |
| `PATCH` | `/api/admin/unknown-items/{id}` | Cambia el estado de un item desconocido (pendiente → añadido/rechazado) |
| `DELETE` | `/api/admin/unknown-items/{id}` | Elimina un item desconocido |
| `DELETE` | `/api/admin/unknown-items` | Elimina varios items desconocidos por ID |
| `GET` | `/api/admin/factors` | Lista todos los factores de emisión (con búsqueda) |
| `POST` | `/api/admin/factors` | Crea un nuevo factor de emisión |
| `PATCH` | `/api/admin/factors/{id}` | Actualiza un factor de emisión existente |
| `DELETE` | `/api/admin/factors/{id}` | Elimina un factor de emisión permanentemente |
| `POST` | `/api/admin/seed-upsert` | Sincroniza los factores de `seed_data.py` con la BD (soporta `?dry_run=true`) |
| `GET` | `/health` | Healthcheck (sin autenticación) — usado por Railway |

---

## 🗄️ Modelo de datos

```
emission_factors   — factores de CO₂ por categoría (seed inicial + gestionables desde el panel admin)
activities         — registro de actividades del usuario (texto original + timestamp)
emissions          — resultado del cálculo: quantity × factor_kg_co2e  (nunca generado por LLM)
user_memory        — hábitos y preferencias del usuario (clave-valor por user_id)
unknown_items       — términos mencionados por usuarios sin categoría conocida, en cola de revisión admin
```

---

## ⚙️ Variables de entorno

### Backend (`carbon-agent/backend/.env`)

```env
OPENAI_API_KEY=sk-...                         # Requerida
OPENAI_MODEL=gpt-4o-mini                      # Modelo a usar (por defecto)
DATABASE_URL=sqlite:///./carbon_agent.db      # Default SQLite (MVP) — PostgreSQL en producción
APP_ENV=development
APP_DEBUG=true
FRONTEND_URL=                                 # Orígenes CORS de producción (coma-separados)
ADMIN_TOKEN=change-me                         # Reservado para endpoints protegidos por token
AUTH0_DOMAIN=                                 # ej: dev-xxxxx.us.auth0.com
AUTH0_AUDIENCE=                               # ej: https://planet-pulse-api
```

### Frontend (`carbon-agent/frontend/.env.local`)

```env
VITE_API_URL=                                 # Vacío en dev (proxy de Vite) · URL de Railway en producción
VITE_AUTH0_DOMAIN=
VITE_AUTH0_CLIENT_ID=
VITE_AUTH0_AUDIENCE=
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

## ☁️ Despliegue

Backend y frontend se despliegan como dos servicios independientes en **Railway** (Nixpacks), cada uno con su propio `railway.toml`:

- **Backend** — `uvicorn main:app --host 0.0.0.0 --port $PORT`, healthcheck en `/health`, base de datos PostgreSQL en producción
- **Frontend** — `npm install && npm run build`, servido estáticamente con `npx serve dist --single`

El CORS del backend acepta explícitamente `FRONTEND_URL` (uno o varios orígenes separados por coma) y, además, cualquier subdominio `*.up.railway.app` mediante `allow_origin_regex`.

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
  │MemoryService│  ← carga home_city, work_place, commute_km, pending_activity, porciones
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
