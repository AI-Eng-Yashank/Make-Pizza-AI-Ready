"""
Phase 2 & 3: LangGraph Agents

Pizza ordering agent and scheduling agent using LangGraph.
"""

import os
import json
from typing import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from mcp_client import SimpleMCPClient
from tools import PizzaMCPTools, SchedulingTools

load_dotenv()


class AgentState(TypedDict):
    """Shared state between agents."""
    messages: Annotated[Sequence[BaseMessage], "Conversation history"]
    order_info: dict
    current_agent: str
    completed: bool


def get_llm():
    """Initialize the Groq LLM."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=api_key
    )


class PizzaAgent:
    """Agent for handling pizza orders."""
    
    def __init__(self, mcp_client: SimpleMCPClient):
        self.mcp_client = mcp_client
        self.llm = get_llm()
        self.tools = []
    
    async def initialize(self):
        """Initialize with MCP tools."""
        pizza_tools = PizzaMCPTools(self.mcp_client)
        await pizza_tools.initialize()
        self.tools = pizza_tools.get_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        return self
    
    async def process(self, state: AgentState) -> AgentState:
        """Process user request."""
        messages = list(state["messages"])
        
        response = await self.llm_with_tools.ainvoke(messages)
        messages.append(response)
        
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                for tool in self.tools:
                    if tool.name == tool_name:
                        result = await tool.ainvoke(tool_args)
                        messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tool_call["id"]
                        ))
                        
                        if "create_order" in tool_name:
                            try:
                                order_data = json.loads(result)
                                state["order_info"] = order_data
                            except json.JSONDecodeError:
                                pass
                        break
            
            final_response = await self.llm_with_tools.ainvoke(messages)
            messages.append(final_response)
        
        return {
            **state,
            "messages": messages,
            "current_agent": "pizza"
        }


class SchedulingAgent:
    """Agent for scheduling deliveries."""
    
    def __init__(self):
        self.llm = get_llm()
        self.tools = SchedulingTools.get_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    async def process(self, state: AgentState) -> AgentState:
        """Process scheduling based on order info."""
        messages = list(state["messages"])
        order_info = state.get("order_info", {})
        
        if order_info:
            context = f"""An order has been placed and needs to be scheduled:

ORDER DETAILS:
- Order ID: {order_info.get('order_id', 'unknown')}
- Pizza Type: {order_info.get('pizza_type', 'unknown')}
- Size: {order_info.get('size', 'large')}
- Total Price: ${order_info.get('total_price', 0)}
- ETA: {order_info.get('eta_minutes', 30)} minutes

YOUR TASKS (do ALL of these):
1. Use schedule_delivery tool to save the order and create a calendar event
2. Use create_calendar_event tool to add this delivery to Google Calendar
3. Use send_notification tool to notify the customer

Make sure to create the Google Calendar event for the delivery!"""
            
            messages.append(HumanMessage(content=context))
        
        response = await self.llm_with_tools.ainvoke(messages)
        messages.append(response)
        
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                for tool in self.tools:
                    if tool.name == tool_name:
                        result = await tool.ainvoke(tool_args)
                        messages.append(ToolMessage(
                            content=result,
                            tool_call_id=tool_call["id"]
                        ))
                        break
            
            final_response = await self.llm_with_tools.ainvoke(messages)
            messages.append(final_response)
        
        return {
            **state,
            "messages": messages,
            "current_agent": "scheduling",
            "completed": True
        }


async def build_workflow(mcp_client: SimpleMCPClient) -> StateGraph:
    """Build the LangGraph workflow."""
    
    pizza_agent = await PizzaAgent(mcp_client).initialize()
    scheduling_agent = SchedulingAgent()
    
    async def pizza_node(state: AgentState) -> AgentState:
        return await pizza_agent.process(state)
    
    async def scheduling_node(state: AgentState) -> AgentState:
        return await scheduling_agent.process(state)
    
    def should_schedule(state: AgentState) -> Literal["scheduling", "end"]:
        order_info = state.get("order_info", {})
        if order_info and order_info.get("order_id"):
            return "scheduling"
        return "end"
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("pizza", pizza_node)
    workflow.add_node("scheduling", scheduling_node)
    
    workflow.set_entry_point("pizza")
    
    workflow.add_conditional_edges(
        "pizza",
        should_schedule,
        {
            "scheduling": "scheduling",
            "end": END
        }
    )
    workflow.add_edge("scheduling", END)
    
    return workflow.compile()


def format_message(msg: BaseMessage) -> str:
    """Format a message for display."""
    if isinstance(msg, HumanMessage):
        return f"User: {msg.content}"
    elif isinstance(msg, AIMessage):
        content = msg.content if msg.content else "[Tool calls]"
        return f"Assistant: {content}"
    elif isinstance(msg, ToolMessage):
        return f"Tool: {msg.content[:200]}..."
    return f"{type(msg).__name__}: {msg.content}"


async def run_conversation(workflow, user_message: str):
    """Run a conversation through the workflow."""
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "order_info": {},
        "current_agent": "",
        "completed": False
    }
    
    print(f"\n{'='*60}")
    print(f"User: {user_message}")
    print(f"{'='*60}")
    
    async for event in workflow.astream(initial_state):
        for node_name, node_state in event.items():
            print(f"\n[{node_name.upper()} AGENT]")
            
            messages = node_state.get("messages", [])
            for msg in messages[-3:]:
                print(format_message(msg))
            
            if node_state.get("order_info"):
                print(f"\nOrder: {json.dumps(node_state['order_info'], indent=2)}")
    
    print(f"\n{'='*60}")