"""
Punto de entrada asíncrono del agente.

Arma el grafo con persistencia (AsyncSqliteSaver, la versión asíncrona de
SqliteSaver — coherente con el resto del proyecto, que usa asyncio de
punta a punta) y expone preguntar(), que envía una consulta dentro de
una sesión identificada por thread_id.

Al pasar el mismo thread_id en llamadas sucesivas, el checkpointer lee
el historial de mensajes previo desde el archivo .sqlite antes de
procesar la nueva pregunta — el agente "recuerda" la conversación, tanto
dentro de una misma ejecución del script como entre corridas distintas
(porque el archivo .sqlite queda en disco).
"""

import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph import build_graph

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "checkpoints.sqlite")

# Techo de pasos del grafo por invocación. Sin este límite, un agente que
# entra en un ciclo de razonamiento defectuoso (por ejemplo, llamando a
# una herramienta una y otra vez sin converger) podría loopear
# indefinidamente, generando costos inesperados de API. Es uno de los
# "errores comunes a evitar" que marca la consigna.
RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", "10"))


def _mensaje_a_dict(mensaje) -> Dict[str, Any]:
    """Convierte un mensaje de LangChain a un dict serializable, para armar la traza en JSON."""
    base: Dict[str, Any] = {
        "tipo": mensaje.__class__.__name__,
        "contenido": mensaje.content,
    }

    tool_calls = getattr(mensaje, "tool_calls", None)
    if tool_calls:
        base["tool_calls"] = [
            {"nombre": tc["name"], "argumentos": tc["args"]} for tc in tool_calls
        ]

    if isinstance(mensaje, ToolMessage):
        base["herramienta"] = mensaje.name

    return base


async def preguntar(pregunta: str, thread_id: str) -> List[Dict[str, Any]]:
    """
    Envía una pregunta al agente dentro de una sesión de razonamiento
    (thread_id) y devuelve la traza completa de la conversación.

    Args:
        pregunta: consulta del usuario en lenguaje natural
        thread_id: identificador de sesión. Usar el mismo thread_id en
                   llamadas sucesivas hace que el agente recuerde el
                   historial completo de esa conversación.

    Returns:
        Lista de mensajes serializados de TODA la conversación en ese
        thread (incluyendo turnos anteriores, si los hubo): mensaje del
        usuario, llamadas a herramientas, resultados de herramientas, y
        la respuesta final del agente.
    """
    logger.info(f"[{thread_id}] Pregunta: {pregunta}")

    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        grafo = build_graph(checkpointer)
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": RECURSION_LIMIT,
        }

        resultado = await grafo.ainvoke(
            {"messages": [HumanMessage(content=pregunta)]},
            config=config,
        )

        mensajes = resultado["messages"]
        logger.info(f"[{thread_id}] Respuesta final: {mensajes[-1].content}")

        return [_mensaje_a_dict(m) for m in mensajes]
