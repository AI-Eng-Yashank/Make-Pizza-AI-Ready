"""
MCP Client Wrapper

Provides a client interface to connect to MCP servers and execute tools.
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class MCPTool:
    """Represents an MCP tool."""
    name: str
    description: str
    input_schema: dict


class MCPClient:
    """Client for communicating with MCP servers via stdio."""
    
    def __init__(self, server_script: str):
        self.server_script = server_script
        self.process: Optional[subprocess.Popen] = None
        self.tools: dict[str, MCPTool] = {}
        self._request_id = 0
    
    async def connect(self):
        """Start the MCP server process."""
        self.process = subprocess.Popen(
            [sys.executable, self.server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pizza-agent", "version": "1.0.0"}
        })
        
        response = await self._send_request("tools/list", {})
        if response and "tools" in response:
            for tool in response["tools"]:
                self.tools[tool["name"]] = MCPTool(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {})
                )
        
        return self
    
    async def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request to the MCP server."""
        if not self.process:
            raise RuntimeError("Not connected to MCP server")
        
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line)
                return response.get("result")
        except Exception as e:
            print(f"MCP communication error: {e}")
        
        return None
    
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call an MCP tool."""
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if response and "content" in response:
            for content in response["content"]:
                if content.get("type") == "text":
                    return content.get("text", "")
        
        return json.dumps(response) if response else '{"error": "No response"}'
    
    def list_tools(self) -> list[MCPTool]:
        """Get list of available tools."""
        return list(self.tools.values())
    
    async def disconnect(self):
        """Close the MCP server connection."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None


class SimpleMCPClient:
    """
    Simplified MCP client using HTTP calls to the underlying API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.tools: dict[str, dict] = {}
    
    async def connect(self):
        """Initialize the client with available tools from OpenAPI spec."""
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/openapi.json")
                spec = response.json()
                
                for path, methods in spec.get("paths", {}).items():
                    for method, operation in methods.items():
                        if method in ["get", "post", "put", "patch", "delete"]:
                            op_id = operation.get("operationId", f"{method}_{path}")
                            self.tools[op_id] = {
                                "name": op_id,
                                "description": operation.get("summary", ""),
                                "method": method.upper(),
                                "path": path,
                                "operation": operation
                            }
        except Exception as e:
            print(f"Failed to fetch OpenAPI spec: {e}")
        
        return self
    
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool by making the corresponding HTTP request."""
        import httpx
        
        tool = self.tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Tool '{tool_name}' not found"})
        
        method = tool["method"]
        path = tool["path"]
        
        for key, value in arguments.items():
            if "{" + key + "}" in path:
                path = path.replace("{" + key + "}", str(value))
        
        url = f"{self.base_url}{path}"
        
        try:
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(url, params=arguments, timeout=30)
                elif method == "POST":
                    response = await client.post(url, json=arguments, timeout=30)
                elif method == "PATCH":
                    response = await client.patch(url, json=arguments, timeout=30)
                elif method == "DELETE":
                    response = await client.delete(url, timeout=30)
                else:
                    response = await client.request(method, url, json=arguments, timeout=30)
                
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
        except httpx.HTTPStatusError as e:
            return json.dumps({"error": str(e), "status_code": e.response.status_code})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def list_tools(self) -> list[dict]:
        """Get list of available tools."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "method": t["method"],
                "path": t["path"]
            }
            for t in self.tools.values()
        ]
    
    async def disconnect(self):
        """Clean up resources."""
        pass
