"""
Mission Pizza - Streamlit Web UI

Web interface showing system stages and order flow.
"""

import streamlit as st
import asyncio
import subprocess
import sys
import time
import json
import requests

st.set_page_config(
    page_title="Mission Pizza",
    page_icon="🍕",
    layout="wide"
)

st.markdown("""
<style>
    .stage-box { padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
    .stage-pending { background-color: #f0f0f0; }
    .stage-running { background-color: #fff3cd; }
    .stage-complete { background-color: #d4edda; }
    .stage-error { background-color: #f8d7da; }
</style>
""", unsafe_allow_html=True)

if "api_process" not in st.session_state:
    st.session_state.api_process = None
if "stages" not in st.session_state:
    st.session_state.stages = {
        "api": "pending",
        "generator": "pending",
        "pizza_agent": "pending",
        "scheduling_agent": "pending"
    }
if "messages" not in st.session_state:
    st.session_state.messages = []
if "order_info" not in st.session_state:
    st.session_state.order_info = None
if "system_ready" not in st.session_state:
    st.session_state.system_ready = False


def render_stage(name: str, status: str, description: str):
    """Render a stage indicator."""
    icons = {"pending": "○", "running": "◐", "complete": "●", "error": "✗"}
    colors = {"pending": "#6c757d", "running": "#ffc107", "complete": "#28a745", "error": "#dc3545"}
    
    icon = icons.get(status, "?")
    color = colors.get(status, "#6c757d")
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; padding: 0.75rem; 
                border-left: 4px solid {color}; background: #fafafa; 
                margin-bottom: 0.5rem; border-radius: 0 4px 4px 0;">
        <span style="font-size: 1.2rem; margin-right: 0.75rem;">{icon}</span>
        <div>
            <strong>{name}</strong><br>
            <small style="color: #666;">{description}</small>
        </div>
    </div>
    """, unsafe_allow_html=True)


def check_api():
    try:
        return requests.get("http://localhost:8000/menu", timeout=2).status_code == 200
    except:
        return False


def start_api():
    if st.session_state.api_process is None:
        kwargs = {}
        if sys.platform == "win32":
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        st.session_state.api_process = subprocess.Popen(
            [sys.executable, "mock_api.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs
        )
        
        # Wait for API to be ready
        for _ in range(30):
            if check_api():
                return True
            time.sleep(1)
        return False
    return check_api()


def stop_api():
    if st.session_state.api_process:
        st.session_state.api_process.terminate()
        st.session_state.api_process.wait()
        st.session_state.api_process = None


def run_generator():
    result = subprocess.run(
        [sys.executable, "generator.py",
         "http://localhost:8000/openapi.json",
         "http://localhost:8000",
         "generated_mcp_server.py"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


async def run_workflow(user_message: str, status_cb):
    from mcp_client import SimpleMCPClient
    from agents import build_workflow
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    
    messages = []
    order_info = {}
    
    status_cb("pizza_agent", "running")
    mcp_client = SimpleMCPClient("http://localhost:8000")
    await mcp_client.connect()
    
    workflow = await build_workflow(mcp_client)
    
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "order_info": {},
        "current_agent": "",
        "completed": False
    }
    
    messages.append({"role": "user", "content": user_message})
    
    async for event in workflow.astream(initial_state):
        for node_name, node_state in event.items():
            if node_name == "pizza":
                status_cb("pizza_agent", "running")
            elif node_name == "scheduling":
                status_cb("pizza_agent", "complete")
                status_cb("scheduling_agent", "running")
            
            for msg in node_state.get("messages", []):
                if isinstance(msg, AIMessage) and msg.content:
                    messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, ToolMessage):
                    messages.append({"role": "tool", "content": msg.content})
            
            if node_state.get("order_info"):
                order_info = node_state["order_info"]
    
    status_cb("scheduling_agent", "complete")
    await mcp_client.disconnect()
    
    return messages, order_info


# UI Layout
st.title("Mission Pizza")
st.markdown("*OpenAPI to MCP Transformation Demo*")

col_status, col_main = st.columns([1, 2])

with col_status:
    st.subheader("System Status")
    
    stages = [
        ("Phase 0: Legacy API", "api", "FastAPI backend"),
        ("Phase 1: MCP Generator", "generator", "OpenAPI to MCP"),
        ("Phase 2: Pizza Agent", "pizza_agent", "Order processing"),
        ("Phase 3: Scheduling Agent", "scheduling_agent", "Delivery coordination"),
    ]
    
    for name, key, desc in stages:
        render_stage(name, st.session_state.stages[key], desc)
    
    st.divider()
    
    if not st.session_state.system_ready:
        if st.button("Start System", type="primary", use_container_width=True):
            with st.spinner("Starting API..."):
                st.session_state.stages["api"] = "running"
                if start_api():
                    st.session_state.stages["api"] = "complete"
                else:
                    st.session_state.stages["api"] = "error"
                    st.error("Failed to start API")
                    st.stop()
            
            with st.spinner("Generating MCP Server..."):
                st.session_state.stages["generator"] = "running"
                success, output = run_generator()
                if success:
                    st.session_state.stages["generator"] = "complete"
                    st.session_state.system_ready = True
                else:
                    st.session_state.stages["generator"] = "error"
                    st.error(f"Failed: {output}")
            
            st.rerun()
    else:
        if st.button("Stop System", use_container_width=True):
            stop_api()
            st.session_state.system_ready = False
            st.session_state.stages = {k: "pending" for k in st.session_state.stages}
            st.session_state.messages = []
            st.session_state.order_info = None
            st.rerun()
    
    if st.session_state.order_info:
        st.divider()
        st.subheader("Order Details")
        info = st.session_state.order_info
        st.markdown(f"""
        **Order ID:** `{info.get('order_id', 'N/A')}`  
        **Status:** {info.get('status', 'N/A')}  
        **Pizza:** {info.get('pizza_type', 'N/A')}  
        **Size:** {info.get('size', 'N/A')}  
        **ETA:** {info.get('eta_minutes', 'N/A')} min  
        **Total:** ${info.get('total_price', 0):.2f}
        """)

with col_main:
    st.subheader("Order Interface")
    
    if not st.session_state.system_ready:
        st.info("Click 'Start System' to begin.")
    else:
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                st.markdown(f"**You:** {content}")
            elif role == "assistant":
                st.markdown(f"**Assistant:** {content}")
            elif role == "tool":
                with st.expander("Tool Result"):
                    st.code(content[:500])
        
        st.divider()
        
        st.markdown("**Quick Orders:**")
        cols = st.columns(3)
        quick_orders = ["Large pepperoni pizza", "Two medium margheritas", "Show me the menu"]
        
        selected = None
        for i, order in enumerate(quick_orders):
            if cols[i].button(order, use_container_width=True):
                selected = order
        
        user_input = st.text_input("Or type:", placeholder="I'd like to order...")
        submit = st.button("Send", type="primary")
        
        message = selected or (user_input if submit and user_input else None)
        
        if message:
            st.session_state.stages["pizza_agent"] = "pending"
            st.session_state.stages["scheduling_agent"] = "pending"
            
            def update(stage, status):
                st.session_state.stages[stage] = status
            
            with st.spinner("Processing..."):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    messages, order_info = loop.run_until_complete(run_workflow(message, update))
                    loop.close()
                    
                    st.session_state.messages = messages
                    st.session_state.order_info = order_info if order_info else None
                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.code(traceback.format_exc())
            
            st.rerun()

st.divider()
st.caption("Mission Pizza Demo | Phases: API → Generator → Pizza Agent → Scheduling Agent")
