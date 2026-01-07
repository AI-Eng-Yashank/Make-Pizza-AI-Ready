"""
LangChain Tool Wrappers

Bridges MCP tools to LangChain's tool interface.
Uses REAL external MCP servers (Filesystem, Memory) when available.
"""

import asyncio
import json
from typing import Any, Optional
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model


def create_langchain_tool_from_mcp(
    name: str,
    description: str,
    parameters: dict,
    call_fn
) -> BaseTool:
    """Create a LangChain tool from MCP tool definition."""
    
    fields = {}
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])
    
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_desc = prop_schema.get("description", "")
        prop_default = prop_schema.get("default")
        
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        python_type = type_map.get(prop_type, str)
        
        if prop_name in required:
            fields[prop_name] = (python_type, Field(description=prop_desc))
        else:
            if prop_default is not None:
                fields[prop_name] = (Optional[python_type], Field(default=prop_default, description=prop_desc))
            else:
                fields[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))
    
    if fields:
        args_schema = create_model(f"{name}Input", **fields)
    else:
        args_schema = None
    
    async def async_run(**kwargs) -> str:
        return await call_fn(name, kwargs)
    
    def sync_run(**kwargs) -> str:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(call_fn(name, kwargs))
        finally:
            loop.close()
    
    return StructuredTool(
        name=name,
        description=description,
        func=sync_run,
        coroutine=async_run,
        args_schema=args_schema
    )


class PizzaMCPTools:
    """Collection of pizza MCP tools wrapped for LangChain."""
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self._tools: list[BaseTool] = []
    
    async def initialize(self):
        """Initialize tools from MCP client."""
        await self.mcp_client.connect()
        
        for tool_info in self.mcp_client.list_tools():
            tool = self._create_tool(tool_info)
            self._tools.append(tool)
        
        return self
    
    def _create_tool(self, tool_info: dict) -> BaseTool:
        """Create a LangChain tool from tool info."""
        name = tool_info["name"]
        description = tool_info["description"]
        parameters = self._infer_parameters(tool_info)
        
        return create_langchain_tool_from_mcp(
            name=name,
            description=description,
            parameters=parameters,
            call_fn=self.mcp_client.call_tool
        )
    
    def _infer_parameters(self, tool_info: dict) -> dict:
        """Infer parameter schema from tool info."""
        path = tool_info.get("path", "")
        method = tool_info.get("method", "GET")
        
        properties = {}
        required = []
        
        import re
        path_params = re.findall(r"\{(\w+)\}", path)
        for param in path_params:
            properties[param] = {
                "type": "string",
                "description": f"Path parameter: {param}"
            }
            required.append(param)
        
        if method == "POST":
            if "order" in tool_info["name"].lower():
                properties.update({
                    "pizza_type": {
                        "type": "string",
                        "description": "Type of pizza (e.g., margherita, pepperoni)"
                    },
                    "size": {
                        "type": "string",
                        "description": "Size: small, medium, or large",
                        "default": "large"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of pizzas",
                        "default": 1
                    },
                    "notes": {
                        "type": "string",
                        "description": "Special instructions"
                    }
                })
                required.append("pizza_type")
        
        return {"properties": properties, "required": required}
    
    def get_tools(self) -> list[BaseTool]:
        """Get all available tools."""
        return self._tools


class SchedulingTools:
    """
    External MCP scheduling tools.
    
    Uses REAL official MCP servers:
    - @modelcontextprotocol/server-filesystem (for order receipts)
    - @modelcontextprotocol/server-memory (for order history)
    
    Falls back to local implementation if Node.js/npx not available.
    """
    
    @staticmethod
    def get_tools() -> list[BaseTool]:
        """Get scheduling tools using real MCP servers."""
        
        async def schedule_delivery(
            order_id: str,
            pizza_type: str,
            eta_minutes: int = 30,
            total_price: float = 0.0
        ) -> str:
            """
            Schedule pizza delivery using REAL external MCP servers.
            
            Uses:
            - Filesystem MCP: Saves order receipt to ./orders/
            - Memory MCP: Stores order in knowledge graph
            """
            from real_mcp import get_external_mcp
            
            order_info = {
                "order_id": order_id,
                "pizza_type": pizza_type,
                "eta_minutes": eta_minutes,
                "total_price": total_price,
                "status": "confirmed"
            }
            
            try:
                mcp_manager = await get_external_mcp()
                result = await mcp_manager.schedule_delivery(order_info)
                return json.dumps(result, indent=2)
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "error": str(e),
                    "fallback": "Using local scheduling"
                })
        
        async def save_order_receipt(order_id: str, order_data: str) -> str:
            """
            Save order receipt using Filesystem MCP server.
            
            This uses the REAL @modelcontextprotocol/server-filesystem.
            """
            from real_mcp import get_external_mcp
            
            try:
                order_info = json.loads(order_data)
                order_info["order_id"] = order_id
                
                mcp_manager = await get_external_mcp()
                result = await mcp_manager.save_order_receipt(order_info)
                return json.dumps(result, indent=2)
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e)})
        
        async def get_order_history() -> str:
            """
            Get order history from Memory MCP knowledge graph.
            
            This uses the REAL @modelcontextprotocol/server-memory.
            """
            from real_mcp import get_external_mcp
            
            try:
                mcp_manager = await get_external_mcp()
                result = await mcp_manager.get_order_history()
                return json.dumps(result, indent=2)
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e)})
        
        async def send_notification(
            recipient: str,
            message: str,
            notification_type: str = "sms"
        ) -> str:
            """Send notification to customer."""
            # Simulated notification (would integrate with real service)
            from datetime import datetime
            result = {
                "status": "sent",
                "type": notification_type,
                "recipient": recipient,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(result, indent=2)
        
        async def create_calendar_event(
            order_id: str,
            pizza_type: str,
            eta_minutes: int = 30
        ) -> str:
            """
            Create delivery event in Google Calendar using REAL Google Calendar MCP.
            
            Requires:
            - Google Cloud Project with Calendar API enabled
            - OAuth credentials configured
            - GOOGLE_OAUTH_CREDENTIALS environment variable
            """
            from real_mcp import get_external_mcp
            
            order_info = {
                "order_id": order_id,
                "pizza_type": pizza_type,
                "eta_minutes": eta_minutes
            }
            
            try:
                mcp_manager = await get_external_mcp()
                result = await mcp_manager.create_calendar_event(order_info)
                return json.dumps(result, indent=2)
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e)})
        
        # Input schemas
        class ScheduleDeliveryInput(BaseModel):
            order_id: str = Field(description="The order ID")
            pizza_type: str = Field(description="Type of pizza ordered")
            eta_minutes: int = Field(default=30, description="Estimated delivery time in minutes")
            total_price: float = Field(default=0.0, description="Total order price")
        
        class SaveReceiptInput(BaseModel):
            order_id: str = Field(description="Order ID")
            order_data: str = Field(description="JSON string of order data")
        
        class SendNotificationInput(BaseModel):
            recipient: str = Field(description="Phone, email, or channel")
            message: str = Field(description="Notification message")
            notification_type: str = Field(default="sms", description="Type: sms, email, slack")
        
        class CreateCalendarEventInput(BaseModel):
            order_id: str = Field(description="Order ID for the delivery")
            pizza_type: str = Field(description="Type of pizza ordered")
            eta_minutes: int = Field(default=30, description="Estimated delivery time")
        
        def make_sync(coro_fn):
            def wrapper(**kwargs):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro_fn(**kwargs))
                finally:
                    loop.close()
            return wrapper
        
        return [
            StructuredTool(
                name="schedule_delivery",
                description="Schedule pizza delivery using REAL external MCP servers (Filesystem MCP for receipts, Memory MCP for history, Google Calendar MCP for events)",
                func=make_sync(schedule_delivery),
                coroutine=schedule_delivery,
                args_schema=ScheduleDeliveryInput
            ),
            StructuredTool(
                name="create_calendar_event",
                description="Create delivery event in Google Calendar using REAL Google Calendar MCP (@cocal/google-calendar-mcp)",
                func=make_sync(create_calendar_event),
                coroutine=create_calendar_event,
                args_schema=CreateCalendarEventInput
            ),
            StructuredTool(
                name="save_order_receipt",
                description="Save order receipt using the official Filesystem MCP server (@modelcontextprotocol/server-filesystem)",
                func=make_sync(save_order_receipt),
                coroutine=save_order_receipt,
                args_schema=SaveReceiptInput
            ),
            StructuredTool(
                name="get_order_history",
                description="Get order history from Memory MCP knowledge graph (@modelcontextprotocol/server-memory)",
                func=make_sync(get_order_history),
                coroutine=get_order_history,
                args_schema=None
            ),
            StructuredTool(
                name="send_notification",
                description="Send notification to customer via SMS, email, or Slack",
                func=make_sync(send_notification),
                coroutine=send_notification,
                args_schema=SendNotificationInput
            )
        ]