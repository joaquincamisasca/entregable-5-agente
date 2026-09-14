# Agente de Razonamiento Cíclico con Memoria Persistente

Agente construido con **LangGraph**: decide autónomamente cuándo usar
herramientas (sin ningún `if/else` manual), razona en varios pasos
encadenados (patrón ReAct), y recuerda el historial de la conversación
entre invocaciones gracias a persistencia con **SQLite**.

**Módulo 5, Pre-entrega 5** - Programa de AI Engineering @ CodeHouse

---

## 🎯 Arquitectura

```
        START
          │
          ▼
     ┌─────────┐   ¿tool_calls en el último mensaje?
     │ agente  │──────────────┐
     └─────────┘              │ sí
          ▲                   ▼
          │            ┌──────────────┐
          └────────────│ herramientas │
                        └──────────────┘
          │ no
          ▼
         END
```

El nodo **agente** invoca al LLM con las herramientas vinculadas
(`llm.bind_tools()`). La arista condicional (`tools_condition`)
inspecciona automáticamente el último mensaje: si el LLM pidió usar una
herramienta, rutea al nodo **herramientas**; si no, el grafo termina. El
resultado de la herramienta vuelve al nodo agente, que puede razonar de
nuevo con esa información — cerrando el ciclo ReAct. Ningún paso de esta
decisión está hardcodeado: el LLM decide todo basándose en el prompt del
usuario y en los docstrings de las herramientas.

---

## 📋 Estructura del Proyecto

```
entregable_5_agente/
├── tools.py            # Herramientas del agente (@tool + docstrings descriptivos)
├── graph.py              # StateGraph: nodo agente + nodo herramientas + arista condicional
├── agent.py                # Punto de entrada async + persistencia (AsyncSqliteSaver)
├── main.py                   # 3 demos: multi-paso, memoria, ciclo de retorno
├── traces/                     # Trazas de ejecución de ejemplo (.json)
│   └── trace_ejemplo_consigna.json
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Instalación

### 1. Entorno virtual y dependencias

```bash
cd entregable_5_agente
python -m venv venv
venv\Scripts\activate      # Windows. Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Instalar y configurar Ollama (LLM 100% gratis y local)

Por defecto, este agente usa **Ollama** para no depender de ninguna API
paga.

1. Descargá Ollama desde [ollama.com/download](https://ollama.com/download)
   e instalalo. Queda corriendo en segundo plano automáticamente.
2. Descargá un modelo que soporte **tool calling** (no todos lo
   soportan):
   ```bash
   ollama pull llama3.2
   ```
3. Listo — no hace falta ninguna API key.

Si preferís usar Claude o GPT-4o (generalmente más confiables llamando
herramientas que los modelos chicos locales), copiá `.env.example` a
`.env`, cambiá `GENERATION_PROVIDER` a `anthropic` u `openai`, y completá
la API key correspondiente.

---

## ▶️ Cómo correrlo

```bash
python main.py
```

Esto corre 3 escenarios de prueba (ver detalle abajo) e imprime en
consola la traza ReAct de cada uno, guardando además una copia en JSON
dentro de `/traces`.

---

## 🧪 Los 3 escenarios de prueba

### 1. Razonamiento multi-paso (`demo_razonamiento_multipaso`)

Pregunta: *"¿Cuántos pedidos tuvo Carlos López y cuál fue el total?"*

El agente solo tiene el **nombre** del cliente, no su ID numérico. Para
responder, necesita encadenar **2 llamadas a herramientas**:

1. `buscar_cliente_por_nombre("Carlos López")` → obtiene `cliente_id=102`
2. `buscar_pedidos(102)` → obtiene `{"pedidos": 3, "total": 14500}`

Recién con esos dos resultados el agente arma la respuesta final. Esto
demuestra el razonamiento multi-paso que pide la consigna.

### 2. Memoria persistente (`demo_memoria_persistente`)

Pregunta de seguimiento, en el **mismo `thread_id`** que la demo 1: *"¿Y
cuál de sus pedidos fue el más caro?"*

El agente responde correctamente sin que se le repita de quién se está
hablando — recupera el contexto (que el cliente en cuestión es Carlos
López / cliente_id 102) desde el historial persistido en SQLite.

### 3. Ciclo de retorno (`demo_ciclo_de_retorno`)

Pregunta: *"¿Cuántos pedidos tuvo el cliente Pedro Ramírez?"* (no existe
en la base de datos ficticia).

`buscar_cliente_por_nombre` devuelve un error con sugerencias de
nombres existentes. El agente no inventa una respuesta: usa esa
información para pedirle aclaración al usuario o señalar que ese
cliente no existe, mostrando los nombres disponibles.

---

## 💾 Persistencia (Resiliencia de Estado)

La persistencia usa `AsyncSqliteSaver` (versión asíncrona de
`SqliteSaver`, coherente con el resto del proyecto que usa `asyncio` de
punta a punta), que guarda el estado completo de cada `thread_id` en un
archivo `.sqlite` en disco.

Esto significa que la memoria **no se pierde ni siquiera si cerrás el
script y lo volvés a correr**: mientras uses el mismo `thread_id`, el
agente retoma la conversación exactamente donde quedó. Se verificó esto
de forma directa: se corrió el grafo en un proceso de Python, se cerró
por completo, y se volvió a abrir en un proceso nuevo apuntando al mismo
archivo `.sqlite` — el historial de mensajes seguía ahí.

```python
from agent import preguntar

# Primera pregunta en una sesión nueva
traza1 = await preguntar("¿Cuántos pedidos tuvo Carlos López?", thread_id="sesion-1")

# ... podés cerrar el script acá y volver a correrlo más tarde ...

# Segunda pregunta, MISMO thread_id: el agente recuerda la conversación anterior
traza2 = await preguntar("¿Y cuál fue el más caro?", thread_id="sesion-1")
```

---

## ⚠️ Errores comunes que este proyecto evita explícitamente

| Error común | Cómo se evita acá |
|---|---|
| Docstrings vagos (el agente no usa la herramienta esperada) | Cada `@tool` en `tools.py` explica cuándo usarla, qué argumentos espera, y qué forma tiene la respuesta en éxito y en error |
| Bucles infinitos sin límite de recursión | `RECURSION_LIMIT=10` configurado en `agent.py`, pasado en cada invocación (`config={"recursion_limit": ...}`) |
| Estado sucio (el historial crece sin límite) | Cada `thread_id` es una conversación separada; para una nueva conversación simplemente se usa un `thread_id` nuevo, en vez de acumular todo en una sola sesión indefinidamente |

---

## 📊 Configuración

| Variable de entorno | Default | Descripción |
|---|---|---|
| `GENERATION_PROVIDER` | `ollama` | `ollama` (gratis, local), `anthropic` u `openai` |
| `OLLAMA_MODEL` | `llama3.2` | Modelo de Ollama (debe soportar tool calling) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | - | Requeridas solo si se usa ese proveedor |
| `CHECKPOINT_DB_PATH` | `checkpoints.sqlite` | Archivo SQLite donde se persiste el estado |
| `RECURSION_LIMIT` | `10` | Techo de pasos del grafo por invocación |

---

## ✅ Checklist de la consigna

| Requisito | Dónde está |
|---|---|
| Autonomía (sin rutas if/else manuales) | `graph.py` → `tools_condition` decide automáticamente |
| Ciclo de retorno ante error/info incompleta | `tools.py` → errores con sugerencias; demo 3 en `main.py` |
| Resiliencia de estado (memoria con thread_id) | `agent.py` → `AsyncSqliteSaver`; demo 2 en `main.py` |
| Python 3.12, type hints, asyncio | Todo el proyecto usa `async def` / `await` y anotaciones de tipo |
| `StateGraph` que hereda de `MessagesState` | `graph.py` → `StateGraph(MessagesState)` |
| Nodo modelo + nodo herramientas + arista condicional (`tools_condition`) | `graph.py` → `build_graph()` |
| Al menos 1 herramienta con `@tool` y docstring descriptivo | `tools.py` → 2 herramientas |
| `llm.bind_tools()` | `graph.py` → `_nodo_agente()` |
| Persistencia con `SqliteSaver` | `agent.py` → `AsyncSqliteSaver` |
| Prueba con ≥2 llamadas a herramienta (multi-paso) | `main.py` → `demo_razonamiento_multipaso()` |
| `recursion_limit` definido | `agent.py` → `RECURSION_LIMIT=10` |
| Traza de ejecución en `.json` | `traces/trace_ejemplo_consigna.json` |
| Repo público sin API keys (usa `.env`) | Todos los módulos leen de `os.getenv()` |

---

**Listo para escalar a agentes con flujos de trabajo más largos y con intervención humana. 🚀**
