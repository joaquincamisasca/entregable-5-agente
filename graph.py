"""
Definición del grafo del agente (StateGraph de LangGraph).

Arquitectura:

    START -> [agente] --tiene tool_calls?--> [herramientas] -> [agente] -> ...
                |                                                  |
                +-------------------- no -------------------------> END

El nodo "agente" llama al LLM con las herramientas vinculadas
(llm.bind_tools()). Si el LLM decide que necesita una herramienta, la
arista condicional (tools_condition) lo detecta automáticamente —
inspeccionando si el último mensaje tiene tool_calls— y rutea hacia el
nodo "herramientas", que las ejecuta. El resultado vuelve al nodo
"agente", que puede razonar de nuevo con esa información nueva (llamar a
otra herramienta, o ya responder). Este ciclo es lo que le da al agente
capacidad de razonamiento multi-paso (patrón ReAct) sin ningún if/else
manual: la decisión de cuándo usar una herramienta la toma el LLM,
inspeccionando únicamente el prompt y los docstrings de las herramientas.
"""

import os
from typing import Optional

from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from tools import TOOLS

# Proveedor de generación por default. "ollama" es gratis y corre local
# (requiere Ollama instalado y corriendo, con un modelo que soporte tool
# calling — ver README.md). Se puede cambiar a "anthropic" u "openai"
# seteando GENERATION_PROVIDER en el .env.
GENERATION_PROVIDER = os.getenv("GENERATION_PROVIDER", "ollama")


def get_llm(
    provider: str = GENERATION_PROVIDER,
    model: Optional[str] = None,
    temperature: float = 0.0,
):
    """Crea el chat model de LangChain para el proveedor pedido."""
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model, temperature=temperature, api_key=os.getenv("OPENAI_API_KEY"))

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        return ChatAnthropic(
            model=model, temperature=temperature, api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        return ChatOllama(model=model, temperature=temperature)

    else:
        raise ValueError(f"Proveedor no soportado: {provider}")


SYSTEM_PROMPT = (
    "Sos un asistente interno de atención al cliente. Tenés acceso a "
    "herramientas para consultar clientes y pedidos en la base de datos "
    "de la empresa. Usá las herramientas cuando necesites datos "
    "concretos — nunca inventes cliente_id, cantidades de pedidos ni "
    "montos. Si una herramienta devuelve un error (por ejemplo, un "
    "cliente que no existe), no te rindas ni inventes una respuesta: "
    "mostrale al usuario las sugerencias o coincidencias que te haya "
    "devuelto la herramienta y pedile que aclare a quién se refiere, o "
    "intentá de nuevo con un nombre corregido si es evidente cuál era. "
    "Respondé siempre en español, de forma clara y concisa."
)


def _nodo_agente(state: MessagesState) -> dict:
    """
    Nodo del modelo: invoca el LLM (con las herramientas vinculadas)
    sobre el historial de mensajes acumulado hasta el momento.

    LangGraph agrega automáticamente el mensaje devuelto a la lista de
    mensajes del estado (MessagesState usa el reducer add_messages).
    """
    llm = get_llm()
    llm_con_herramientas = llm.bind_tools(TOOLS)

    mensajes = state["messages"]
    # Insertamos el system prompt una sola vez, al principio, si todavía
    # no está presente en el historial.
    if not mensajes or mensajes[0].type != "system":
        from langchain_core.messages import SystemMessage

        mensajes = [SystemMessage(content=SYSTEM_PROMPT), *mensajes]

    respuesta = llm_con_herramientas.invoke(mensajes)
    return {"messages": [respuesta]}


def build_graph(checkpointer=None):
    """
    Arma y compila el StateGraph.

    Args:
        checkpointer: instancia de checkpointer de LangGraph (ej.
                      AsyncSqliteSaver) para persistir el estado entre
                      invocaciones con el mismo thread_id. Si se omite,
                      el grafo funciona pero sin memoria persistente
                      (cada invocación arranca de cero).

    Returns:
        Grafo compilado, listo para invocar con .ainvoke()
    """
    builder = StateGraph(MessagesState)

    builder.add_node("agente", _nodo_agente)
    builder.add_node("herramientas", ToolNode(TOOLS))

    builder.set_entry_point("agente")

    # Arista condicional: tools_condition inspecciona el último mensaje
    # del estado y decide automáticamente el siguiente paso — sin ningún
    # if/else manual escrito por nosotros. Si el LLM pidió usar una
    # herramienta (tool_calls no vacío), rutea a "herramientas"; si no,
    # el grafo termina.
    builder.add_conditional_edges(
        "agente",
        tools_condition,
        {"tools": "herramientas", END: END},
    )

    # Después de ejecutar la herramienta, siempre volvemos al agente para
    # que razone con el resultado nuevo — acá se cierra el ciclo ReAct.
    builder.add_edge("herramientas", "agente")

    return builder.compile(checkpointer=checkpointer)
