"""
Phase 0: Mock Legacy Pizza API

A simple FastAPI backend that simulates the pizza ordering system.
This generates an OpenAPI spec that we'll convert to MCP.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import uuid

app = FastAPI(
    title="Pizza Legacy API",
    description="Legacy pizza ordering system API",
    version="1.0.0"
)

# --- In-Memory Data Store ---
MENU = {
    "margherita": {
        "name": "Margherita",
        "price": 12.00,
        "description": "Classic tomato sauce, mozzarella, fresh basil"
    },
    "pepperoni": {
        "name": "Pepperoni",
        "price": 14.00,
        "description": "Tomato sauce, mozzarella, spicy pepperoni"
    },
    "quattro_formaggi": {
        "name": "Quattro Formaggi",
        "price": 16.00,
        "description": "Mozzarella, gorgonzola, parmesan, fontina"
    },
    "vegetarian": {
        "name": "Vegetarian",
        "price": 13.00,
        "description": "Tomato sauce, mozzarella, bell peppers, mushrooms, olives"
    }
}

ORDERS: dict = {}


# --- Request/Response Schemas ---
class PizzaSize(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class OrderRequest(BaseModel):
    pizza_type: str = Field(..., description="Type of pizza (e.g., margherita, pepperoni)")
    size: PizzaSize = Field(default=PizzaSize.large, description="Size of the pizza")
    quantity: int = Field(default=1, ge=1, le=10, description="Number of pizzas")
    notes: Optional[str] = Field(default=None, description="Special instructions")


class OrderResponse(BaseModel):
    order_id: str
    status: str
    pizza_type: str
    size: str
    quantity: int
    total_price: float
    eta_minutes: int
    notes: Optional[str] = None


class MenuItemResponse(BaseModel):
    name: str
    price: float
    description: str


# --- API Endpoints ---
@app.get("/menu", response_model=dict[str, MenuItemResponse], tags=["Menu"])
async def get_menu():
    """
    Get the complete pizza menu.
    
    Returns all available pizzas with their names, prices, and descriptions.
    """
    return MENU


@app.get("/menu/{pizza_type}", response_model=MenuItemResponse, tags=["Menu"])
async def get_menu_item(pizza_type: str):
    """
    Get details for a specific pizza type.
    
    Args:
        pizza_type: The type of pizza to look up (e.g., margherita, pepperoni)
    """
    if pizza_type not in MENU:
        raise HTTPException(status_code=404, detail=f"Pizza type '{pizza_type}' not found")
    return MENU[pizza_type]


@app.post("/orders", response_model=OrderResponse, tags=["Orders"])
async def create_order(order: OrderRequest):
    """
    Place a new pizza order.
    
    Creates an order and returns confirmation with order ID and ETA.
    """
    if order.pizza_type not in MENU:
        raise HTTPException(status_code=400, detail=f"Invalid pizza type: {order.pizza_type}")
    
    order_id = str(uuid.uuid4())[:8]
    
    # Calculate price based on size
    base_price = MENU[order.pizza_type]["price"]
    size_multiplier = {"small": 0.8, "medium": 1.0, "large": 1.2}
    total_price = base_price * size_multiplier[order.size.value] * order.quantity
    
    order_data = {
        "order_id": order_id,
        "status": "confirmed",
        "pizza_type": order.pizza_type,
        "size": order.size.value,
        "quantity": order.quantity,
        "total_price": round(total_price, 2),
        "eta_minutes": 25 + (order.quantity * 5),
        "notes": order.notes
    }
    
    ORDERS[order_id] = order_data
    return OrderResponse(**order_data)


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order(order_id: str):
    """
    Get the status of an existing order.
    
    Args:
        order_id: The unique order identifier
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return OrderResponse(**ORDERS[order_id])


@app.patch("/orders/{order_id}/cancel", tags=["Orders"])
async def cancel_order(order_id: str):
    """
    Cancel an existing order.
    
    Args:
        order_id: The unique order identifier
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    
    if ORDERS[order_id]["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="Order already cancelled")
    
    ORDERS[order_id]["status"] = "cancelled"
    return {"message": f"Order {order_id} has been cancelled", "order_id": order_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
