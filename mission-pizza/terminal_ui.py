"""
Mission Pizza - Terminal UI

Terminal interface with stage indicators and colored output.
"""

import asyncio
import subprocess
import sys
import time
import json
import os


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    print(f"""
{Colors.BOLD}+--------------------------------------------------------------+
|                      MISSION PIZZA                           |
|              OpenAPI to MCP Transformation Demo              |
+--------------------------------------------------------------+{Colors.ENDC}
""")


def print_stage(number: int, name: str, status: str, details: str = ""):
    """Print a stage with status indicator."""
    status_symbols = {
        "pending": f"{Colors.DIM}[ ]{Colors.ENDC}",
        "running": f"{Colors.YELLOW}[~]{Colors.ENDC}",
        "complete": f"{Colors.GREEN}[x]{Colors.ENDC}",
        "error": f"{Colors.RED}[!]{Colors.ENDC}"
    }
    
    symbol = status_symbols.get(status, "[ ]")
    color = Colors.GREEN if status == "complete" else Colors.YELLOW if status == "running" else Colors.DIM
    
    print(f"  {symbol} Phase {number}: {color}{name}{Colors.ENDC}")
    if details and status != "complete":
        print(f"           {Colors.DIM}{details}{Colors.ENDC}")


def print_stages(stages: dict):
    """Print all stages."""
    stage_info = [
        (0, "Legacy API", stages.get("api", "pending"), "FastAPI backend"),
        (1, "MCP Generator", stages.get("generator", "pending"), "OpenAPI to MCP"),
        (2, "Pizza Agent", stages.get("pizza_agent", "pending"), "Order processing"),
        (3, "Scheduling Agent", stages.get("scheduling_agent", "pending"), "Delivery coordination"),
    ]
    
    print(f"\n{Colors.BOLD}System Status:{Colors.ENDC}")
    print("  " + "-" * 50)
    for num, name, status, desc in stage_info:
        print_stage(num, name, status, desc)
    print("  " + "-" * 50)


def print_message(role: str, content: str):
    """Print a chat message."""
    if role == "user":
        print(f"\n{Colors.BLUE}You:{Colors.ENDC} {content}")
    elif role == "assistant":
        print(f"\n{Colors.GREEN}Assistant:{Colors.ENDC} {content}")
    elif role == "tool":
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"\n{Colors.YELLOW}[Tool]{Colors.ENDC} {Colors.DIM}{content}{Colors.ENDC}")


def print_order_info(order_info: dict):
    """Print order details box."""
    if not order_info:
        return
    
    print(f"\n{Colors.BOLD}Order Confirmation:{Colors.ENDC}")
    print("  +" + "-" * 40 + "+")
    print(f"  | Order ID:  {order_info.get('order_id', 'N/A'):<27}|")
    print(f"  | Status:    {order_info.get('status', 'N/A'):<27}|")
    print(f"  | Pizza:     {order_info.get('pizza_type', 'N/A'):<27}|")
    print(f"  | Size:      {order_info.get('size', 'N/A'):<27}|")
    print(f"  | ETA:       {order_info.get('eta_minutes', 'N/A')} minutes{' '*18}|")
    print(f"  | Total:     ${order_info.get('total_price', 0):.2f}{' '*23}|")
    print("  +" + "-" * 40 + "+")


class PizzaTerminalUI:
    def __init__(self):
        self.stages = {
            "api": "pending",
            "generator": "pending",
            "pizza_agent": "pending",
            "scheduling_agent": "pending"
        }
        self.api_process = None
        self.messages = []
        self.order_info = None
    
    def update_display(self):
        """Refresh the terminal display."""
        clear_screen()
        print_header()
        print_stages(self.stages)
        
        if self.messages:
            print(f"\n{Colors.BOLD}Conversation:{Colors.ENDC}")
            for msg in self.messages[-6:]:
                print_message(msg["role"], msg["content"])
        
        if self.order_info:
            print_order_info(self.order_info)
    
    def start_api(self) -> bool:
        """Start the mock API."""
        self.stages["api"] = "running"
        self.update_display()
        print(f"\n{Colors.CYAN}Starting API...{Colors.ENDC}")
        
        # Platform-specific options
        kwargs = {}
        if sys.platform == "win32":
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        self.api_process = subprocess.Popen(
            [sys.executable, "mock_api.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs
        )
        
        # Wait for API with retry
        import requests
        print(f"  Waiting for API", end="", flush=True)
        for _ in range(30):
            try:
                response = requests.get("http://localhost:8000/menu", timeout=2)
                if response.status_code == 200:
                    print(f" {Colors.GREEN}OK{Colors.ENDC}")
                    self.stages["api"] = "complete"
                    return True
            except:
                pass
            print(".", end="", flush=True)
            time.sleep(1)
        
        print(f" {Colors.RED}TIMEOUT{Colors.ENDC}")
        self.stages["api"] = "error"
        return False
    
    def run_generator(self) -> bool:
        """Run the MCP generator."""
        self.stages["generator"] = "running"
        self.update_display()
        print(f"\n{Colors.CYAN}Generating MCP server...{Colors.ENDC}")
        
        result = subprocess.run(
            [sys.executable, "generator.py",
             "http://localhost:8000/openapi.json",
             "http://localhost:8000",
             "generated_mcp_server.py"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.stages["generator"] = "complete"
            print(f"{Colors.GREEN}Generated: generated_mcp_server.py{Colors.ENDC}")
            return True
        
        self.stages["generator"] = "error"
        print(f"{Colors.RED}Error: {result.stderr}{Colors.ENDC}")
        return False
    
    async def run_agents(self, user_message: str):
        """Run the agent workflow."""
        from mcp_client import SimpleMCPClient
        from agents import build_workflow
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        
        self.messages = [{"role": "user", "content": user_message}]
        self.stages["pizza_agent"] = "running"
        self.update_display()
        
        print(f"\n{Colors.CYAN}Connecting to MCP...{Colors.ENDC}")
        mcp_client = SimpleMCPClient("http://localhost:8000")
        await mcp_client.connect()
        
        tools = [t["name"] for t in mcp_client.list_tools()]
        print(f"Tools: {', '.join(tools)}")
        
        workflow = await build_workflow(mcp_client)
        
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "order_info": {},
            "current_agent": "",
            "completed": False
        }
        
        print(f"\n{Colors.CYAN}Processing...{Colors.ENDC}")
        
        async for event in workflow.astream(initial_state):
            for node_name, node_state in event.items():
                if node_name == "pizza":
                    self.stages["pizza_agent"] = "running"
                elif node_name == "scheduling":
                    self.stages["pizza_agent"] = "complete"
                    self.stages["scheduling_agent"] = "running"
                
                for msg in node_state.get("messages", []):
                    if isinstance(msg, AIMessage) and msg.content:
                        self.messages.append({"role": "assistant", "content": msg.content})
                        self.update_display()
                    elif isinstance(msg, ToolMessage):
                        self.messages.append({"role": "tool", "content": msg.content})
                
                if node_state.get("order_info"):
                    self.order_info = node_state["order_info"]
        
        self.stages["scheduling_agent"] = "complete"
        self.update_display()
        
        await mcp_client.disconnect()
    
    def stop(self):
        """Clean up."""
        if self.api_process:
            self.api_process.terminate()
            self.api_process.wait()
    
    def run(self):
        """Main loop."""
        try:
            self.update_display()
            
            print(f"\n{Colors.BOLD}Initializing...{Colors.ENDC}")
            if not self.start_api():
                print(f"{Colors.RED}Failed to start API{Colors.ENDC}")
                return
            
            if not self.run_generator():
                print(f"{Colors.RED}Failed to generate MCP{Colors.ENDC}")
                return
            
            self.update_display()
            
            print(f"\n{Colors.BOLD}Ready. Enter your order (or 'quit'):{Colors.ENDC}")
            
            while True:
                print()
                user_input = input(f"{Colors.BLUE}You: {Colors.ENDC}").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                asyncio.run(self.run_agents(user_input))
                
                print(f"\n{Colors.DIM}Enter another order or 'quit'{Colors.ENDC}")
        
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Interrupted{Colors.ENDC}")
        finally:
            print(f"\n{Colors.CYAN}Shutting down...{Colors.ENDC}")
            self.stop()
            print(f"{Colors.GREEN}Done.{Colors.ENDC}")


def main():
    ui = PizzaTerminalUI()
    ui.run()


if __name__ == "__main__":
    main()
