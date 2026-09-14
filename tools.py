"""
Herramientas del agente.

La consigna advierte que el error más común en agentes con LangGraph no
está en la lógica del grafo, sino en docstrings vagos: el LLM decide qué
herramienta usar (y con qué argumentos) basándose ÚNICAMENTE en la
descripción de la función, nunca en su implementación. Por eso cada
docstring acá es deliberadamente explícito sobre cuándo usar la
herramienta, qué devuelve en cada caso (éxito y error), y cómo
combinarla con las demás.
"""

from typing import Dict, List, Union

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Base de datos ficticia en memoria (simula una BD real de clientes/pedidos)
# ---------------------------------------------------------------------------

_CLIENTES: Dict[int, str] = {
    101: "Ana García",
    102: "Carlos López",
    103: "Marta Fernández",
}

_PEDIDOS: Dict[int, List[Dict[str, Union[int, float]]]] = {
    101: [{"id": 1, "monto": 3200.0}, {"id": 2, "monto": 4800.0}],
    102: [{"id": 1, "monto": 5000.0}, {"id": 2, "monto": 5500.0}, {"id": 3, "monto": 4000.0}],
    103: [{"id": 1, "monto": 12000.0}],
}


@tool
def buscar_cliente_por_nombre(nombre: str) -> dict:
    """
    Busca el ID interno (cliente_id) de un cliente a partir de su nombre,
    consultando la base de datos de clientes de la empresa.

    USAR ESTA HERRAMIENTA SIEMPRE que el usuario mencione un cliente por
    su NOMBRE (no por número de ID) y necesites averiguar sus pedidos,
    facturación o cualquier otro dato asociado a su cliente_id. Es el
    primer paso obligatorio antes de poder llamar a buscar_pedidos()
    cuando solo tenés el nombre del cliente.

    Args:
        nombre: nombre completo o parcial del cliente a buscar
                (ej: "Carlos López" o simplemente "Carlos")

    Returns:
        - Si hay exactamente una coincidencia: {"cliente_id": int, "nombre": str}
        - Si no hay ninguna coincidencia: {"error": str, "sugerencias": [nombres existentes]}
          En este caso, mostrale las sugerencias al usuario y preguntale
          si se refería a alguno de esos nombres, en vez de inventar un
          cliente_id.
        - Si hay varias coincidencias ambiguas: {"error": str, "coincidencias": [...]}
          En este caso, pedile al usuario que aclare a cuál de esos
          clientes se refiere.
    """
    nombre_normalizado = nombre.strip().lower()
    coincidencias = [
        (cid, nom) for cid, nom in _CLIENTES.items() if nombre_normalizado in nom.lower()
    ]

    if len(coincidencias) == 1:
        cliente_id, nombre_completo = coincidencias[0]
        return {"cliente_id": cliente_id, "nombre": nombre_completo}

    if len(coincidencias) > 1:
        return {
            "error": f"Hay {len(coincidencias)} clientes que coinciden con '{nombre}'.",
            "coincidencias": [
                {"cliente_id": cid, "nombre": nom} for cid, nom in coincidencias
            ],
        }

    return {
        "error": f"No se encontró ningún cliente con el nombre '{nombre}'.",
        "sugerencias": list(_CLIENTES.values()),
    }


@tool
def buscar_pedidos(cliente_id: int) -> dict:
    """
    Devuelve la cantidad de pedidos y el monto total facturado a un
    cliente, identificado por su cliente_id NUMÉRICO (no por nombre).

    Si solo tenés el nombre del cliente y no su cliente_id numérico, usá
    primero buscar_cliente_por_nombre() para obtenerlo — no inventes ni
    supongas un cliente_id.

    Args:
        cliente_id: ID numérico interno del cliente (obtenido previamente
                    de buscar_cliente_por_nombre, o indicado directamente
                    por el usuario)

    Returns:
        - Si el cliente existe: {"cliente_id": int, "pedidos": int,
          "total": float, "detalle": [{"id": int, "monto": float}, ...]}
        - Si no existe ningún cliente con ese ID: {"error": str}
    """
    if cliente_id not in _PEDIDOS:
        return {"error": f"No existe ningún cliente con ID {cliente_id}."}

    pedidos = _PEDIDOS[cliente_id]
    total = sum(p["monto"] for p in pedidos)

    return {
        "cliente_id": cliente_id,
        "pedidos": len(pedidos),
        "total": total,
        "detalle": pedidos,
    }


TOOLS = [buscar_cliente_por_nombre, buscar_pedidos]
