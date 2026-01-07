"""
Real MCP Server Integration

Connects to REAL official MCP servers:
1. @modelcontextprotocol/server-filesystem - For saving order receipts
2. @modelcontextprotocol/server-memory - For order history/knowledge graph
3. @cocal/google-calendar-mcp - For Google Calendar integration (optional)

Prerequisites:
    npm install -g npx
    (Node.js must be installed)

For Google Calendar:
    - Create Google Cloud Project
    - Enable Google Calendar API
    - Create OAuth credentials
    - Set GOOGLE_OAUTH_CREDENTIALS environment variable

These are REAL MCP servers from:
- https://github.com/modelcontextprotocol/servers
- https://github.com/nspady/google-calendar-mcp
"""

import asyncio
import json
import subprocess
import sys
import os
import shutil
from typing import Optional, Any
from pathlib import Path
from datetime import datetime, timedelta


def get_npx_command():
    """Get the correct npx command for the current platform."""
    if sys.platform == "win32":
        # On Windows, try to find npx.cmd
        npx_cmd = shutil.which("npx.cmd") or shutil.which("npx")
        if npx_cmd:
            return npx_cmd
        # Fallback to common paths
        common_paths = [
            r"C:\Program Files\nodejs\npx.cmd",
            r"C:\Program Files (x86)\nodejs\npx.cmd",
            os.path.expandvars(r"%APPDATA%\npm\npx.cmd"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return "npx.cmd"  # Hope it's in PATH
    else:
        return "npx"


NPX_COMMAND = get_npx_command()


class RealMCPClient:
    """
    Client that connects to real MCP servers via stdio transport.
    
    This uses the official MCP JSON-RPC protocol over stdin/stdout.
    """
    
    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._initialized = False
        self.env = None  # Custom environment variables
    
    async def connect(self) -> bool:
        """Start the MCP server process and initialize."""
        try:
            # Replace 'npx' with the correct command for this platform
            cmd = self.command.copy()
            if cmd[0] == "npx":
                cmd[0] = NPX_COMMAND
            
            print(f"  Starting {self.name}: {' '.join(cmd)}")
            
            # Windows-specific subprocess settings
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # Use custom env if provided, otherwise use current env
            process_env = self.env if self.env else os.environ.copy()
            
            # Start the MCP server process
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=process_env
            )
            
            # Give the process a moment to start
            await asyncio.sleep(1)
            
            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                print(f"  {self.name} process exited: {stderr}")
                return False
            
            # Send initialize request
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "mission-pizza-agent",
                    "version": "1.0.0"
                }
            })
            
            if init_response:
                # Send initialized notification
                await self._send_notification("notifications/initialized", {})
                self._initialized = True
                print(f"  Connected to {self.name} MCP server")
                return True
            
            return False
            
        except FileNotFoundError as e:
            print(f"  ERROR: Could not find npx: {e}")
            print(f"  Make sure Node.js is installed and npx is in PATH")
            return False
        except Exception as e:
            print(f"  ERROR connecting to {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send JSON-RPC request and get response."""
        if not self.process or self.process.poll() is not None:
            return None
        
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        
        try:
            # Send request
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
            
            # Read response
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                if "error" in response:
                    print(f"  MCP Error: {response['error']}")
                    return None
                return response.get("result", {})
            
        except Exception as e:
            print(f"  Request error: {e}")
        
        return None
    
    async def _send_notification(self, method: str, params: dict):
        """Send JSON-RPC notification (no response expected)."""
        if not self.process:
            return
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        try:
            self.process.stdin.write(json.dumps(notification) + "\n")
            self.process.stdin.flush()
        except:
            pass
    
    async def list_tools(self) -> list[dict]:
        """Get available tools from the MCP server."""
        response = await self._send_request("tools/list", {})
        if response and "tools" in response:
            return response["tools"]
        return []
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        if response and "content" in response:
            # Extract text content
            for item in response["content"]:
                if item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except:
                        return {"result": item["text"]}
            return response
        
        return {"error": "No response from tool"}
    
    async def disconnect(self):
        """Stop the MCP server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None


class FilesystemMCPServer:
    """
    Wrapper for the official @modelcontextprotocol/server-filesystem.
    
    This is a REAL MCP server that provides:
    - read_file: Read file contents
    - write_file: Write content to files
    - list_directory: List directory contents
    - create_directory: Create directories
    - move_file: Move/rename files
    - search_files: Search for files
    - get_file_info: Get file metadata
    """
    
    def __init__(self, allowed_directories: list[str]):
        self.allowed_dirs = [str(Path(d).absolute()) for d in allowed_directories]
        self.client: Optional[RealMCPClient] = None
    
    async def connect(self) -> bool:
        """Connect to the filesystem MCP server."""
        command = ["npx", "-y", "@modelcontextprotocol/server-filesystem"] + self.allowed_dirs
        self.client = RealMCPClient("filesystem", command)
        return await self.client.connect()
    
    async def write_file(self, path: str, content: str) -> dict:
        """Write content to a file."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("write_file", {
            "path": path,
            "content": content
        })
    
    async def read_file(self, path: str) -> dict:
        """Read content from a file."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("read_file", {
            "path": path
        })
    
    async def list_directory(self, path: str) -> dict:
        """List directory contents."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("list_directory", {
            "path": path
        })
    
    async def list_tools(self) -> list[dict]:
        """Get available filesystem tools."""
        if not self.client:
            return []
        return await self.client.list_tools()
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            await self.client.disconnect()


class MemoryMCPServer:
    """
    Wrapper for the official @modelcontextprotocol/server-memory.
    
    This is a REAL MCP server that provides a knowledge graph for:
    - create_entities: Create new entities in the graph
    - create_relations: Create relationships between entities
    - search_nodes: Search for entities
    - read_graph: Read the entire knowledge graph
    - delete_entities: Remove entities
    
    Perfect for storing order history and customer data!
    """
    
    def __init__(self):
        self.client: Optional[RealMCPClient] = None
    
    async def connect(self) -> bool:
        """Connect to the memory MCP server."""
        command = ["npx", "-y", "@modelcontextprotocol/server-memory"]
        self.client = RealMCPClient("memory", command)
        return await self.client.connect()
    
    async def create_entities(self, entities: list[dict]) -> dict:
        """Create entities in the knowledge graph."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("create_entities", {
            "entities": entities
        })
    
    async def create_relations(self, relations: list[dict]) -> dict:
        """Create relations between entities."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("create_relations", {
            "relations": relations
        })
    
    async def search_nodes(self, query: str) -> dict:
        """Search for entities in the graph."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("search_nodes", {
            "query": query
        })
    
    async def read_graph(self) -> dict:
        """Read the entire knowledge graph."""
        if not self.client:
            return {"error": "Not connected"}
        return await self.client.call_tool("read_graph", {})
    
    async def list_tools(self) -> list[dict]:
        """Get available memory tools."""
        if not self.client:
            return []
        return await self.client.list_tools()
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            await self.client.disconnect()


class GoogleCalendarMCPServer:
    """
    Wrapper for Google Calendar MCP Server.
    
    Uses @cocal/google-calendar-mcp for REAL Google Calendar integration.
    
    Tools provided:
    - list_events: List calendar events
    - create_event: Create new calendar event
    - update_event: Update existing event
    - delete_event: Delete an event
    - get_freebusy: Check availability
    
    Requirements:
    - Google Cloud Project with Calendar API enabled
    - OAuth credentials (gcp-oauth.keys.json)
    - Environment variable: GOOGLE_OAUTH_CREDENTIALS
    
    Setup:
    1. Go to https://console.cloud.google.com
    2. Create project, enable Google Calendar API
    3. Create OAuth 2.0 credentials
    4. Download credentials as gcp-oauth.keys.json
    5. Set GOOGLE_OAUTH_CREDENTIALS=/path/to/gcp-oauth.keys.json
    6. Run: npx @cocal/google-calendar-mcp auth
    """
    
    def __init__(self):
        self.client: Optional[RealMCPClient] = None
        self.credentials_path = os.environ.get("GOOGLE_OAUTH_CREDENTIALS", "")
        self._available = False
    
    async def connect(self) -> bool:
        """Connect to Google Calendar MCP server."""
        if not self.credentials_path:
            print("  Google Calendar: GOOGLE_OAUTH_CREDENTIALS not set (optional)")
            return False
        
        if not Path(self.credentials_path).exists():
            print(f"  Google Calendar: Credentials file not found: {self.credentials_path}")
            return False
        
        try:
            command = ["npx", "-y", "@cocal/google-calendar-mcp"]
            
            # Create client with custom environment
            self.client = RealMCPClient("google-calendar", command)
            self.client.env = os.environ.copy()
            self.client.env["GOOGLE_OAUTH_CREDENTIALS"] = self.credentials_path
            
            if await self.client.connect():
                self._available = True
                return True
        except Exception as e:
            print(f"  Google Calendar: Connection failed: {e}")
        
        return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def list_events(self, time_min: str = None, time_max: str = None, max_results: int = 10) -> dict:
        """List calendar events."""
        if not self.client:
            return {"error": "Google Calendar not connected"}
        
        args = {"maxResults": max_results}
        if time_min:
            args["timeMin"] = time_min
        if time_max:
            args["timeMax"] = time_max
        
        return await self.client.call_tool("list_events", args)
    
    async def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = ""
    ) -> dict:
        """Create a calendar event."""
        if not self.client:
            return {"error": "Google Calendar not connected"}
        
        return await self.client.call_tool("create_event", {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "description": description,
            "location": location
        })
    
    async def get_freebusy(self, time_min: str, time_max: str) -> dict:
        """Check calendar availability."""
        if not self.client:
            return {"error": "Google Calendar not connected"}
        
        return await self.client.call_tool("get_freebusy", {
            "timeMin": time_min,
            "timeMax": time_max
        })
    
    async def list_tools(self) -> list[dict]:
        """Get available calendar tools."""
        if not self.client:
            return []
        return await self.client.list_tools()
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            await self.client.disconnect()


class WeatherMCPServer:
    """
    Wrapper for Weather MCP Server.
    
    Uses @dangahagan/weather-mcp for REAL weather data.
    
    NO API KEY REQUIRED! Uses free NOAA and Open-Meteo APIs.
    
    Tools provided:
    - get_forecast: Get weather forecast for any location
    - get_alerts: Get weather alerts for US states
    - get_current: Get current weather conditions
    
    Creative use for pizza delivery:
    - Check if it's raining (delivery delay warning)
    - Suggest hot/cold drinks based on temperature
    - Weather-based delivery time adjustments
    """
    
    def __init__(self):
        self.client: Optional[RealMCPClient] = None
        self._available = False
    
    async def connect(self) -> bool:
        """Connect to Weather MCP server."""
        try:
            command = ["npx", "-y", "@dangahagan/weather-mcp"]
            self.client = RealMCPClient("weather", command)
            if await self.client.connect():
                self._available = True
                return True
        except Exception as e:
            print(f"  Weather MCP: Connection failed: {e}")
        
        return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def get_forecast(self, latitude: float, longitude: float) -> dict:
        """Get weather forecast for coordinates."""
        if not self.client:
            return {"error": "Weather MCP not connected"}
        
        return await self.client.call_tool("get_forecast", {
            "latitude": latitude,
            "longitude": longitude
        })
    
    async def get_alerts(self, state: str) -> dict:
        """Get weather alerts for a US state."""
        if not self.client:
            return {"error": "Weather MCP not connected"}
        
        return await self.client.call_tool("get_alerts", {
            "state": state
        })
    
    async def list_tools(self) -> list[dict]:
        """Get available weather tools."""
        if not self.client:
            return []
        return await self.client.list_tools()
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            await self.client.disconnect()


class ExternalMCPManager:
    """
    Manages connections to REAL external MCP servers.
    
    Uses official MCP servers:
    - Filesystem MCP: For saving order receipts
    - Memory MCP: For order history knowledge graph
    - Google Calendar MCP: For scheduling deliveries (optional)
    """
    
    def __init__(self, orders_directory: str = "./orders"):
        self.orders_dir = Path(orders_directory).absolute()
        self.orders_dir.mkdir(exist_ok=True)
        
        self.filesystem: Optional[FilesystemMCPServer] = None
        self.memory: Optional[MemoryMCPServer] = None
        self.calendar: Optional[GoogleCalendarMCPServer] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to all external MCP servers."""
        print("\nConnecting to external MCP servers...")
        
        success = True
        
        # Connect to Filesystem MCP
        self.filesystem = FilesystemMCPServer([str(self.orders_dir)])
        if not await self.filesystem.connect():
            print("  WARNING: Filesystem MCP not available (Node.js/npx required)")
            self.filesystem = None
            success = False
        
        # Connect to Memory MCP
        self.memory = MemoryMCPServer()
        if not await self.memory.connect():
            print("  WARNING: Memory MCP not available (Node.js/npx required)")
            self.memory = None
            success = False
        
        # Connect to Google Calendar MCP (optional)
        self.calendar = GoogleCalendarMCPServer()
        if await self.calendar.connect():
            tools = await self.calendar.list_tools()
            print(f"  Google Calendar tools: {[t['name'] for t in tools]}")
        else:
            self.calendar = None
            # Not a failure - calendar is optional
        
        self._connected = success
        
        if success:
            print("  External MCP servers connected!")
            
            if self.filesystem:
                tools = await self.filesystem.list_tools()
                print(f"  Filesystem tools: {[t['name'] for t in tools]}")
            
            if self.memory:
                tools = await self.memory.list_tools()
                print(f"  Memory tools: {[t['name'] for t in tools]}")
        
        return success
    
    async def save_order_receipt(self, order_info: dict) -> dict:
        """
        Save order receipt using Filesystem MCP server.
        """
        order_id = order_info.get("order_id", "unknown")
        filename = f"order_{order_id}.json"
        filepath = str(self.orders_dir / filename)
        
        receipt = {
            **order_info,
            "saved_at": datetime.now().isoformat(),
            "receipt_version": "1.0"
        }
        
        if self.filesystem:
            result = await self.filesystem.write_file(
                filepath,
                json.dumps(receipt, indent=2)
            )
            return {
                "status": "success",
                "method": "filesystem_mcp",
                "path": filepath,
                "result": result
            }
        else:
            Path(filepath).write_text(json.dumps(receipt, indent=2))
            return {
                "status": "success",
                "method": "direct_write",
                "path": filepath
            }
    
    async def store_order_in_memory(self, order_info: dict) -> dict:
        """
        Store order in Memory MCP knowledge graph.
        """
        order_id = order_info.get("order_id", "unknown")
        
        if self.memory:
            entity_result = await self.memory.create_entities([{
                "name": f"Order_{order_id}",
                "entityType": "PizzaOrder",
                "observations": [
                    f"Pizza type: {order_info.get('pizza_type')}",
                    f"Size: {order_info.get('size')}",
                    f"Price: ${order_info.get('total_price')}",
                    f"ETA: {order_info.get('eta_minutes')} minutes",
                    f"Status: {order_info.get('status')}",
                    f"Ordered at: {datetime.now().isoformat()}"
                ]
            }])
            
            return {
                "status": "success",
                "method": "memory_mcp",
                "entity": f"Order_{order_id}",
                "result": entity_result
            }
        else:
            return {
                "status": "skipped",
                "reason": "Memory MCP not available"
            }
    
    async def create_calendar_event(self, order_info: dict) -> dict:
        """
        Create delivery event in Google Calendar using REAL Google Calendar MCP.
        """
        print(f"  Creating calendar event... (calendar available: {self.calendar is not None and self.calendar.is_available if self.calendar else False})")
        
        if not self.calendar or not self.calendar.is_available:
            # Fallback: Return simulated event
            order_id = order_info.get("order_id", "unknown")
            eta = order_info.get("eta_minutes", 30)
            delivery_time = datetime.now() + timedelta(minutes=eta)
            
            return {
                "status": "simulated",
                "reason": "Google Calendar MCP not configured",
                "event": {
                    "summary": f"Pizza Delivery - {order_info.get('pizza_type')}",
                    "scheduled_time": delivery_time.strftime("%I:%M %p"),
                    "order_id": order_id
                }
            }
        
        # Use REAL Google Calendar MCP
        order_id = order_info.get("order_id", "unknown")
        eta = order_info.get("eta_minutes", 30)
        pizza_type = order_info.get("pizza_type", "pizza")
        total_price = order_info.get("total_price", 0)
        
        start_time = datetime.now() + timedelta(minutes=eta)
        end_time = start_time + timedelta(minutes=15)
        
        # Format times for Google Calendar API (ISO 8601)
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        print(f"  Calling Google Calendar MCP create-event tool...")
        
        try:
            # Call the REAL Google Calendar MCP create-event tool
            # calendarId "primary" means the user's main calendar
            result = await self.calendar.client.call_tool("create-event", {
                "calendarId": "primary",
                "summary": f"🍕 Pizza Delivery - {pizza_type.title()}",
                "description": f"Order ID: {order_id}\nPizza: {pizza_type}\nSize: {order_info.get('size', 'large')}\nTotal: ${total_price}\n\nDelivery from Mission Pizza!",
                "start": start_iso,
                "end": end_iso
            })
            
            print(f"  Google Calendar response: {result}")
            
            return {
                "status": "success",
                "method": "google_calendar_mcp",
                "event": {
                    "summary": f"Pizza Delivery - {pizza_type.title()}",
                    "start": start_iso,
                    "end": end_iso,
                    "order_id": order_id
                },
                "mcp_response": result
            }
        except Exception as e:
            print(f"  Google Calendar error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "method": "google_calendar_mcp",
                "error": str(e)
            }
    
    async def get_order_history(self) -> dict:
        """
        Get order history from Memory MCP.
        """
        if self.memory:
            result = await self.memory.search_nodes("Order")
            return {
                "status": "success",
                "method": "memory_mcp",
                "orders": result
            }
        else:
            orders = []
            for f in self.orders_dir.glob("order_*.json"):
                try:
                    orders.append(json.loads(f.read_text()))
                except:
                    pass
            return {
                "status": "success",
                "method": "filesystem_fallback",
                "orders": orders
            }
    
    async def schedule_delivery(self, order_info: dict) -> dict:
        """
        Complete delivery workflow using external MCP servers.
        
        1. Save receipt (Filesystem MCP)
        2. Store in knowledge graph (Memory MCP)
        3. Create calendar event (Google Calendar MCP)
        4. Return confirmation
        """
        results = {}
        
        # 1. Save receipt using Filesystem MCP
        receipt_result = await self.save_order_receipt(order_info)
        results["receipt"] = receipt_result
        
        # 2. Store in Memory MCP knowledge graph
        memory_result = await self.store_order_in_memory(order_info)
        results["memory"] = memory_result
        
        # 3. Create Google Calendar event
        calendar_result = await self.create_calendar_event(order_info)
        results["calendar"] = calendar_result
        
        # 4. Create delivery schedule entry
        order_id = order_info.get("order_id", "unknown")
        eta = order_info.get("eta_minutes", 30)
        
        delivery_time = datetime.now() + timedelta(minutes=eta)
        
        results["delivery"] = {
            "status": "scheduled",
            "order_id": order_id,
            "scheduled_time": delivery_time.strftime("%I:%M %p"),
            "eta_minutes": eta
        }
        
        results["notification"] = {
            "status": "sent",
            "message": f"Your {order_info.get('pizza_type')} pizza will arrive at {delivery_time.strftime('%I:%M %p')}!"
        }
        
        return {
            "status": "success",
            "message": "Delivery scheduled using external MCP servers",
            "details": results
        }
    
    async def disconnect(self):
        """Disconnect from all MCP servers."""
        if self.filesystem:
            await self.filesystem.disconnect()
        if self.memory:
            await self.memory.disconnect()
        if self.calendar:
            await self.calendar.disconnect()


# Singleton instance
external_mcp_manager: Optional[ExternalMCPManager] = None


async def get_external_mcp() -> ExternalMCPManager:
    """Get or create the external MCP manager."""
    global external_mcp_manager
    if external_mcp_manager is None:
        external_mcp_manager = ExternalMCPManager()
        await external_mcp_manager.connect()
    return external_mcp_manager