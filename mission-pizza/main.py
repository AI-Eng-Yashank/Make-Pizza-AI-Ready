"""
Mission Pizza - Main Entry Point

Orchestrates all phases with proper startup handling.
"""

import asyncio
import subprocess
import sys
import time
import requests
from pathlib import Path

API_HOST = "localhost"
API_PORT = 8000
API_URL = f"http://{API_HOST}:{API_PORT}"


def wait_for_api(url: str, timeout: int = 30) -> bool:
    """Wait for API to be ready."""
    print("  Waiting for API to start", end="", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/menu", timeout=2)
            if response.status_code == 200:
                print(" OK")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)
    print(" TIMEOUT")
    return False


def start_mock_api() -> subprocess.Popen:
    """Start the mock legacy API server."""
    print("\n[Phase 0] Starting Mock Pizza API...")
    
    # Platform-specific subprocess options
    kwargs = {}
    if sys.platform == "win32":
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    
    process = subprocess.Popen(
        [sys.executable, "mock_api.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs
    )
    
    if wait_for_api(API_URL):
        print(f"  API running at {API_URL}")
        return process
    else:
        print("  ERROR: API failed to start")
        process.terminate()
        return None


def run_generator():
    """Run the OpenAPI to MCP generator."""
    print("\n[Phase 1] Running MCP Generator...")
    
    # Verify API is accessible
    try:
        response = requests.get(f"{API_URL}/openapi.json", timeout=5)
        response.raise_for_status()
        print("  OpenAPI spec fetched")
    except Exception as e:
        print(f"  ERROR: Cannot reach API: {e}")
        return False
    
    result = subprocess.run(
        [sys.executable, "generator.py", f"{API_URL}/openapi.json", API_URL, "generated_mcp_server.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  Generator error: {result.stderr}")
        return False
    
    print("  Generated: generated_mcp_server.py")
    return True


async def run_agents():
    """Run the agent workflow."""
    from mcp_client import SimpleMCPClient
    from agents import build_workflow, run_conversation
    
    print("\n[Phase 2 & 3] Initializing Agents...")
    
    mcp_client = SimpleMCPClient(API_URL)
    await mcp_client.connect()
    
    tools = [t['name'] for t in mcp_client.list_tools()]
    print(f"  Tools available: {tools}")
    
    workflow = await build_workflow(mcp_client)
    
    print("\n" + "=" * 60)
    print("Ready! Enter your order (or 'quit' to exit)")
    print("Example: 'I want a large pepperoni pizza'")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            await run_conversation(workflow, user_input)
            
        except EOFError:
            break
    
    await mcp_client.disconnect()


def main():
    """Main entry point."""
    print("=" * 60)
    print("       MISSION PIZZA - AI Pizza Ordering System")
    print("=" * 60)
    
    api_process = None
    
    try:
        # Phase 0
        api_process = start_mock_api()
        if api_process is None:
            print("\nCannot continue without API. Exiting.")
            return
        
        # Phase 1
        if not run_generator():
            print("\nCannot continue without MCP server. Exiting.")
            return
        
        # Phase 2 & 3
        asyncio.run(run_agents())
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if api_process:
            print("\nStopping API server...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
        print("Goodbye!")


if __name__ == "__main__":
    main()
