"""
External MCP Server Integration

Integrates with external MCP servers for scheduling functionality.
Options:
1. Google Calendar MCP
2. Filesystem MCP (for saving order receipts)
3. Slack MCP (for notifications)

For demo purposes, we also include a working mock that simulates external MCP behavior.
"""

import json
import asyncio
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


class ExternalMCPClient:
    """
    Client for connecting to external MCP servers.
    
    In production, this would connect to real MCP servers like:
    - Google Calendar MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/google-calendar
    - Slack MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/slack
    - Filesystem MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem
    """
    
    def __init__(self, server_command: list[str] = None):
        self.server_command = server_command
        self.process = None
        self._request_id = 0
    
    async def connect(self):
        """Connect to external MCP server via stdio."""
        if self.server_command:
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Initialize MCP connection
            await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pizza-scheduler", "version": "1.0.0"}
            })
        return self
    
    async def _send_request(self, method: str, params: dict) -> dict:
        """Send JSON-RPC request to MCP server."""
        if not self.process:
            return {"error": "Not connected"}
        
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
            response = self.process.stdout.readline()
            return json.loads(response).get("result", {})
        except Exception as e:
            return {"error": str(e)}
    
    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool on the external MCP server."""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return json.dumps(result, indent=2)
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        if self.process:
            self.process.terminate()
            self.process = None


class FileSystemMCP:
    """
    Simulates Filesystem MCP server for saving order receipts.
    
    In production, use: npx -y @modelcontextprotocol/server-filesystem <path>
    """
    
    def __init__(self, base_path: str = "./orders"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
    
    async def write_file(self, filename: str, content: str) -> dict:
        """Write order receipt to file."""
        filepath = self.base_path / filename
        filepath.write_text(content)
        return {
            "status": "success",
            "path": str(filepath),
            "message": f"File saved: {filename}"
        }
    
    async def read_file(self, filename: str) -> dict:
        """Read order receipt from file."""
        filepath = self.base_path / filename
        if filepath.exists():
            return {
                "status": "success",
                "content": filepath.read_text()
            }
        return {"status": "error", "message": "File not found"}
    
    async def list_files(self) -> dict:
        """List all order receipts."""
        files = [f.name for f in self.base_path.glob("*.json")]
        return {"files": files, "count": len(files)}


class CalendarMCP:
    """
    Simulates Google Calendar MCP server.
    
    In production, use: npx -y @modelcontextprotocol/server-google-calendar
    with proper Google OAuth credentials.
    """
    
    def __init__(self):
        self.events = []
    
    async def create_event(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 30,
        description: str = ""
    ) -> dict:
        """Create a calendar event for delivery."""
        event_id = f"evt_{len(self.events) + 1:04d}"
        
        # Parse or create start time
        if start_time == "now":
            start = datetime.now()
        else:
            try:
                start = datetime.fromisoformat(start_time)
            except:
                start = datetime.now() + timedelta(minutes=30)
        
        end = start + timedelta(minutes=duration_minutes)
        
        event = {
            "id": event_id,
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "description": description,
            "status": "confirmed"
        }
        
        self.events.append(event)
        
        return {
            "status": "success",
            "event": event,
            "message": f"Calendar event created: {title} at {start.strftime('%I:%M %p')}"
        }
    
    async def list_events(self, date: str = None) -> dict:
        """List calendar events."""
        return {
            "events": self.events,
            "count": len(self.events)
        }
    
    async def delete_event(self, event_id: str) -> dict:
        """Delete a calendar event."""
        self.events = [e for e in self.events if e["id"] != event_id]
        return {"status": "deleted", "event_id": event_id}


class NotificationMCP:
    """
    Simulates notification service (Slack/Email/SMS MCP).
    
    In production, use:
    - Slack: npx -y @modelcontextprotocol/server-slack
    - Or integrate with Twilio, SendGrid, etc.
    """
    
    def __init__(self):
        self.sent_notifications = []
    
    async def send_sms(self, phone: str, message: str) -> dict:
        """Send SMS notification."""
        notification = {
            "type": "sms",
            "to": phone,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "status": "delivered"
        }
        self.sent_notifications.append(notification)
        return notification
    
    async def send_email(self, email: str, subject: str, body: str) -> dict:
        """Send email notification."""
        notification = {
            "type": "email",
            "to": email,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
            "status": "delivered"
        }
        self.sent_notifications.append(notification)
        return notification
    
    async def send_slack(self, channel: str, message: str) -> dict:
        """Send Slack notification."""
        notification = {
            "type": "slack",
            "channel": channel,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "status": "delivered"
        }
        self.sent_notifications.append(notification)
        return notification


class ExternalMCPManager:
    """
    Manages multiple external MCP server connections.
    
    Provides unified interface for:
    - Calendar scheduling
    - File storage (receipts)
    - Notifications
    """
    
    def __init__(self):
        self.calendar = CalendarMCP()
        self.filesystem = FileSystemMCP()
        self.notifications = NotificationMCP()
    
    async def schedule_delivery(self, order_info: dict) -> dict:
        """
        Complete delivery scheduling workflow using external MCP services.
        
        1. Create calendar event
        2. Save order receipt
        3. Send notifications
        """
        order_id = order_info.get("order_id", "unknown")
        pizza_type = order_info.get("pizza_type", "pizza")
        eta_minutes = order_info.get("eta_minutes", 30)
        total_price = order_info.get("total_price", 0)
        
        results = {}
        
        # 1. Create calendar event
        calendar_result = await self.calendar.create_event(
            title=f"Pizza Delivery - {pizza_type.title()}",
            start_time="now",
            duration_minutes=eta_minutes,
            description=f"Order ID: {order_id}\nTotal: ${total_price}"
        )
        results["calendar"] = calendar_result
        
        # 2. Save order receipt
        receipt = {
            "order_id": order_id,
            "pizza_type": pizza_type,
            "total_price": total_price,
            "eta_minutes": eta_minutes,
            "ordered_at": datetime.now().isoformat(),
            "status": "confirmed"
        }
        file_result = await self.filesystem.write_file(
            f"order_{order_id}.json",
            json.dumps(receipt, indent=2)
        )
        results["receipt"] = file_result
        
        # 3. Send notifications
        sms_result = await self.notifications.send_sms(
            phone="+1234567890",
            message=f"Your {pizza_type} pizza order #{order_id} will arrive in {eta_minutes} minutes!"
        )
        results["sms"] = sms_result
        
        email_result = await self.notifications.send_email(
            email="customer@example.com",
            subject=f"Pizza Order Confirmation - #{order_id}",
            body=f"Thank you for your order!\n\nPizza: {pizza_type}\nTotal: ${total_price}\nETA: {eta_minutes} minutes"
        )
        results["email"] = email_result
        
        return {
            "status": "success",
            "message": "Delivery scheduled and notifications sent",
            "details": results
        }
    
    async def get_order_history(self) -> dict:
        """Get all past orders from filesystem."""
        files = await self.filesystem.list_files()
        orders = []
        
        for filename in files.get("files", []):
            result = await self.filesystem.read_file(filename)
            if result.get("status") == "success":
                try:
                    orders.append(json.loads(result["content"]))
                except:
                    pass
        
        return {"orders": orders, "count": len(orders)}


# Singleton instance for use across the application
external_mcp = ExternalMCPManager()