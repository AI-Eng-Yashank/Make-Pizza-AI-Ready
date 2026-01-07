"""
Auto-generated MCP Server from OpenAPI Specification.

Generated from: Pizza Legacy API
Version: 1.0.0
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import httpx
import json

mcp = FastMCP("pizza_mcp")

BASE_URL = "http://localhost:8000"

@mcp.tool(
    name="get_menu_menu_get",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False
    }
)
async def get_menu_menu_get() -> str:
    """
    Get Menu
    """
    url = BASE_URL + '/menu'

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e), "status_code": e.response.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool(
    name="get_menu_item_menu__pizza_type__get",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False
    }
)
async def get_menu_item_menu__pizza_type__get(pizza_type: str) -> str:
    """
    Get Menu Item
    """
    url = BASE_URL + '/menu/' + str(pizza_type)

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e), "status_code": e.response.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool(
    name="create_order_orders_post",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False
    }
)
async def create_order_orders_post(pizza_type: str, size: str = "large", quantity: int = 1, notes: Optional[str] = None) -> str:
    """
    Create Order
    """
    url = BASE_URL + '/orders'
    payload = {
        "pizza_type": pizza_type,
        "size": size,
        "quantity": quantity,
        "notes": notes,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e), "status_code": e.response.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool(
    name="get_order_orders__order_id__get",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False
    }
)
async def get_order_orders__order_id__get(order_id: str) -> str:
    """
    Get Order
    """
    url = BASE_URL + '/orders/' + str(order_id)

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e), "status_code": e.response.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool(
    name="cancel_order_orders__order_id__cancel_patch",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True
    }
)
async def cancel_order_orders__order_id__cancel_patch(order_id: str) -> str:
    """
    Cancel Order
    """
    url = BASE_URL + '/orders/' + str(order_id) + '/cancel'

    try:
        response = httpx.patch(url, timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e), "status_code": e.response.status_code})
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
