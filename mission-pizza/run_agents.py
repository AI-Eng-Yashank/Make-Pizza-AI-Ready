"""
Run Agents - Standalone agent runner

Use this after starting mock_api.py manually in another terminal.
This is useful if you have issues with automatic subprocess startup.

Usage:
    Terminal 1: python mock_api.py
    Terminal 2: python run_agents.py
"""

import asyncio
import subprocess
import sys
import requests

API_URL = "http://localhost:8000"


def check_api():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_URL}/menu", timeout=2)
        return response.status_code == 200
    except:
        return False


def generate_mcp():
    """Generate MCP server from API."""
    print("Generating MCP server...")
    result = subprocess.run(
        [sys.executable, "generator.py", f"{API_URL}/openapi.json", API_URL, "generated_mcp_server.py"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print("Generated: generated_mcp_server.py")
    return True


async def run():
    """Run the agent workflow."""
    from mcp_client import SimpleMCPClient
    from agents import build_workflow, run_conversation
    
    print("Connecting to MCP tools...")
    mcp_client = SimpleMCPClient(API_URL)
    await mcp_client.connect()
    
    tools = [t['name'] for t in mcp_client.list_tools()]
    print(f"Available tools: {tools}")
    
    workflow = await build_workflow(mcp_client)
    
    print("\n" + "=" * 50)
    print("Ready! Enter your order (or 'quit' to exit)")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            await run_conversation(workflow, user_input)
        except (EOFError, KeyboardInterrupt):
            break
    
    await mcp_client.disconnect()
    print("\nGoodbye!")


def main():
    print("=" * 50)
    print("Mission Pizza - Agent Runner")
    print("=" * 50)
    
    # Check if API is running
    print("\nChecking API...")
    if not check_api():
        print("ERROR: API is not running!")
        print("Please start the API first in another terminal:")
        print("  python mock_api.py")
        return
    
    print("API is running.")
    
    # Generate MCP
    if not generate_mcp():
        print("Failed to generate MCP server.")
        return
    
    # Run agents
    asyncio.run(run())


if __name__ == "__main__":
    main()
