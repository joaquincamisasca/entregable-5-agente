"""
Script de prueba del agente. Corre tres escenarios:

1. Razonamiento multi-paso: el agente necesita llamar a la herramienta
   de búsqueda de cliente y DESPUÉS a la de pedidos (2 tool calls en
   cadena) para poder responder.
2. Memoria persistente: una pregunta de seguimiento en el MISMO
   thread_id, que solo se puede responder si el agente recuerda el
   contexto de la conversación anterior.
3. Ciclo de retorno: se pregunta por un cliente que no existe, y se
   verifica que el agente use el error/sugerencias que le devuelve la
   herramienta para pedir aclaración, en vez de inventar una respuesta.

Cada escenario guarda su traza completa (formato ReAct: pregunta, tool
calls, resultados de herramientas, respuesta final) como JSON en /traces.
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from agent import preguntar

load_dotenv()

TRACES_DIR = Path(__file__).parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)


def _guardar_traza(nombre_archivo: str, traza: list) -> None:
    """Guarda la traza de una conversación como JSON legible en /traces."""
    path = TRACES_DIR / f"{nombre_archivo}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(traza, f, indent=2, ensure_ascii=False)
    print(f"✓ Traza guardada en {path.relative_to(Path(__file__).parent)}")


def _imprimir_traza(traza: list) -> None:
    """Imprime la traza en formato ReAct legible en consola."""
    for mensaje in traza:
        tipo = mensaje["tipo"]
        if tipo == "HumanMessage":
            print(f"  Usuario: {mensaje['contenido']}")
        elif tipo == "AIMessage" and mensaje.get("tool_calls"):
            for tc in mensaje["tool_calls"]:
                print(f"  → El agente decide usar la herramienta: {tc['nombre']}({tc['argumentos']})")
        elif tipo == "ToolMessage":
            print(f"  → La herramienta '{mensaje['herramienta']}' devuelve: {mensaje['contenido']}")
        elif tipo == "AIMessage":
            print(f"  Respuesta: {mensaje['contenido']}")


async def demo_razonamiento_multipaso() -> None:
    print(f"\n{'='*70}")
    print("DEMO 1: Razonamiento multi-paso (nombre -> cliente_id -> pedidos)")
    print(f"{'='*70}\n")

    thread_id = "demo-multipaso"
    pregunta = "¿Cuántos pedidos tuvo Carlos López y cuál fue el total?"

    traza = await preguntar(pregunta, thread_id)
    _imprimir_traza(traza)
    _guardar_traza("trace_razonamiento_multipaso", traza)


async def demo_memoria_persistente() -> None:
    print(f"\n{'='*70}")
    print("DEMO 2: Memoria persistente (mismo thread_id, pregunta de seguimiento)")
    print(f"{'='*70}\n")

    # A propósito, MISMO thread_id que la demo 1: el agente debe recordar
    # que ya estábamos hablando de Carlos López / cliente_id 102.
    thread_id = "demo-multipaso"
    pregunta = "¿Y cuál de sus pedidos fue el más caro?"

    traza = await preguntar(pregunta, thread_id)
    _imprimir_traza(traza)
    _guardar_traza("trace_memoria_persistente", traza)


async def demo_ciclo_de_retorno() -> None:
    print(f"\n{'='*70}")
    print("DEMO 3: Ciclo de retorno (cliente inexistente -> el agente pide aclaración)")
    print(f"{'='*70}\n")

    thread_id = "demo-error"
    pregunta = "¿Cuántos pedidos tuvo el cliente Pedro Ramírez?"

    traza = await preguntar(pregunta, thread_id)
    _imprimir_traza(traza)
    _guardar_traza("trace_ciclo_de_retorno", traza)


async def main() -> None:
    await demo_razonamiento_multipaso()
    await demo_memoria_persistente()
    await demo_ciclo_de_retorno()

    print(f"\n{'='*70}")
    print("Demos completadas. Trazas guardadas en /traces")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
