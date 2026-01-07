# Mission Pizza: AI-Ready Pizza Ordering System

A comprehensive system that automatically transforms OpenAPI specifications into MCP (Model Context Protocol) servers, enabling AI agents to interact with legacy REST APIs. This project demonstrates multi-agent orchestration with real external MCP server integration including Google Calendar.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [System Flow](#system-flow)
4. [Module Documentation](#module-documentation)
5. [MCP Server Integration](#mcp-server-integration)
6. [Setup Instructions](#setup-instructions)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)
9. [Technical Decisions](#technical-decisions)
10. [Problems Faced and Solutions](#problems-faced-and-solutions)

---

## Project Overview

### Problem Statement

Legacy pizza ordering systems use traditional REST APIs that are not accessible to AI agents. The goal is to:

1. Automatically convert OpenAPI specifications to MCP servers
2. Build AI agents that can process natural language orders
3. Integrate with external MCP servers for scheduling and notifications
4. Demonstrate agent-to-agent communication

### Solution

This project implements a four-phase system:

- Phase 0: Legacy REST API (FastAPI backend)
- Phase 1: OpenAPI to MCP Generator
- Phase 2: Pizza Ordering Agent (LangGraph + Groq)
- Phase 3: Scheduling Agent with External MCP Servers

### Technologies Used

| Category | Technology | Purpose |
|----------|------------|---------|
| LLM Provider | Groq | Fast inference using llama-3.3-70b-versatile |
| Agent Framework | LangChain | Tool abstraction and LLM integration |
| Orchestration | LangGraph | Multi-agent workflow and state management |
| Protocol | MCP | Model Context Protocol for tool communication |
| Backend | FastAPI | Mock pizza ordering REST API |
| HTTP Client | httpx | Async HTTP requests |
| External MCP | Filesystem MCP | Order receipt storage |
| External MCP | Memory MCP | Knowledge graph for order history |
| External MCP | Google Calendar MCP | Delivery event scheduling |

---

## Architecture

### High-Level Architecture

```
+------------------------------------------------------------------+
|                         USER INPUT                                |
|                "I want a large pepperoni pizza"                   |
+----------------------------------+-------------------------------+
                                   |
                                   v
+------------------------------------------------------------------+
|                      LANGGRAPH WORKFLOW                           |
|                                                                   |
|  +------------------------------------------------------------+  |
|  |                    PIZZA AGENT (Phase 2)                   |  |
|  |                                                            |  |
|  |  - Receives natural language input                         |  |
|  |  - Selects appropriate MCP tools                           |  |
|  |  - Calls Generated MCP Server                              |  |
|  |  - Returns order confirmation with order_id, ETA, price    |  |
|  +-----------------------------+------------------------------+  |
|                                |                                  |
|                                | Agent-to-Agent Communication     |
|                                | (Shared State: order_info)       |
|                                |                                  |
|                                v                                  |
|  +------------------------------------------------------------+  |
|  |                 SCHEDULING AGENT (Phase 3)                 |  |
|  |                                                            |  |
|  |  - Receives order details from Pizza Agent                 |  |
|  |  - Connects to External MCP Servers:                       |  |
|  |    - Filesystem MCP: Save order receipt                    |  |
|  |    - Memory MCP: Store in knowledge graph                  |  |
|  |    - Google Calendar MCP: Create delivery event            |  |
|  |  - Sends customer notification                             |  |
|  +------------------------------------------------------------+  |
+----------------------------------+-------------------------------+
                                   |
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
         v                         v                         v
+------------------+    +------------------+    +------------------+
|   GENERATED      |    |   EXTERNAL MCP   |    |   EXTERNAL MCP   |
|   MCP SERVER     |    |   SERVERS        |    |   (GOOGLE CAL)   |
|   (Phase 1)      |    |                  |    |                  |
|                  |    |  +------------+  |    |  +------------+  |
|  - get_menu      |    |  | Filesystem |  |    |  | Calendar   |  |
|  - create_order  |    |  | MCP        |  |    |  | MCP        |  |
|  - get_order     |    |  +------------+  |    |  +------------+  |
|  - cancel_order  |    |  +------------+  |    |                  |
|                  |    |  | Memory     |  |    |  - list-events   |
+--------+---------+    |  | MCP        |  |    |  - create-event  |
         |              |  +------------+  |    |  - update-event  |
         |              +------------------+    +------------------+
         v
+------------------+
|   LEGACY REST    |
|   API (FastAPI)  |
|                  |
|  GET  /menu      |
|  POST /orders    |
|  GET  /orders/id |
|  PATCH /cancel   |
+------------------+
```

### Component Interaction Diagram

```
+-------------+     +-------------+     +-------------+
|    User     |     |   Pizza     |     | Scheduling  |
|   Input     |     |   Agent     |     |   Agent     |
+------+------+     +------+------+     +------+------+
       |                   |                   |
       | 1. Natural        |                   |
       |    Language       |                   |
       +------------------>|                   |
       |                   |                   |
       |            2. Call MCP Tool           |
       |                   +--------+          |
       |                   |        |          |
       |                   v        |          |
       |            +------+------+ |          |
       |            | Generated   | |          |
       |            | MCP Server  | |          |
       |            +------+------+ |          |
       |                   |        |          |
       |            3. HTTP Request |          |
       |                   v        |          |
       |            +------+------+ |          |
       |            | Legacy API  | |          |
       |            | (FastAPI)   | |          |
       |            +------+------+ |          |
       |                   |        |          |
       |            4. Response     |          |
       |                   |<-------+          |
       |                   |                   |
       |            5. Pass order_info         |
       |                   +------------------>|
       |                   |                   |
       |                   |    6. Call External MCP Servers
       |                   |                   +--------+
       |                   |                   |        |
       |                   |                   v        |
       |                   |    +--------------------+  |
       |                   |    | Filesystem MCP     |  |
       |                   |    | Memory MCP         |  |
       |                   |    | Google Calendar MCP|  |
       |                   |    +--------------------+  |
       |                   |                   |        |
       |                   |    7. Results     |<-------+
       |                   |                   |
       |            8. Final Response          |
       |<------------------+-------------------+
       |                   |                   |
```

### Data Flow Diagram

```
Phase 0: API Startup
+------------------+
| mock_api.py      |
| starts FastAPI   |
| on port 8000     |
+--------+---------+
         |
         v
Phase 1: MCP Generation
+------------------+
| generator.py     |
| fetches OpenAPI  |
| spec from /openapi.json
+--------+---------+
         |
         | Parses endpoints, parameters, schemas
         v
+------------------+
| generated_mcp_   |
| server.py        |
| with @mcp.tool   |
| decorators       |
+--------+---------+
         |
         v
Phase 2: Pizza Agent
+------------------+
| PizzaAgent       |
| - Binds MCP tools|
| - Processes NL   |
| - Places orders  |
+--------+---------+
         |
         | Passes order_info via LangGraph state
         v
Phase 3: Scheduling Agent
+------------------+
| SchedulingAgent  |
| - Filesystem MCP |
| - Memory MCP     |
| - Calendar MCP   |
+------------------+
```

---

## System Flow

### Complete Order Flow

```
Step 1: User Input
+------------------------------------------+
| User: "I want a large pepperoni pizza"   |
+------------------------------------------+
                    |
                    v
Step 2: Pizza Agent Processing
+------------------------------------------+
| - LLM analyzes request                   |
| - Selects create_order tool              |
| - Calls: create_order(pizza_type=        |
|          "pepperoni", size="large")      |
+------------------------------------------+
                    |
                    v
Step 3: Generated MCP Server
+------------------------------------------+
| - Receives tool call                     |
| - Makes HTTP POST to localhost:8000/     |
|   orders                                 |
| - Returns order confirmation             |
+------------------------------------------+
                    |
                    v
Step 4: Order Response
+------------------------------------------+
| {                                        |
|   "order_id": "abc123",                  |
|   "status": "confirmed",                 |
|   "pizza_type": "pepperoni",             |
|   "size": "large",                       |
|   "total_price": 16.80,                  |
|   "eta_minutes": 30                      |
| }                                        |
+------------------------------------------+
                    |
                    v
Step 5: Agent-to-Agent Handoff
+------------------------------------------+
| order_info passed to Scheduling Agent    |
| via LangGraph shared state               |
+------------------------------------------+
                    |
                    v
Step 6: External MCP Server Calls
+------------------------------------------+
| Filesystem MCP:                          |
|   - write_file("orders/order_abc123.json"|
|                                          |
| Memory MCP:                              |
|   - create_entities([{name: "Order_abc123|
|     entityType: "PizzaOrder", ...}])     |
|                                          |
| Google Calendar MCP:                     |
|   - create-event({calendarId: "primary", |
|     summary: "Pizza Delivery...",        |
|     start: "2024-01-06T20:00:00", ...})  |
+------------------------------------------+
                    |
                    v
Step 7: Final Response
+------------------------------------------+
| "Your pepperoni pizza order has been     |
| scheduled. Order ID: abc123. Delivery    |
| in 30 minutes. Calendar event created."  |
+------------------------------------------+
```

---

## Module Documentation

### File Structure

```
mission-pizza/
|
+-- mock_api.py           # Phase 0: Legacy REST API
+-- generator.py          # Phase 1: OpenAPI to MCP converter
+-- generated_mcp_server.py # Auto-generated MCP server
|
+-- mcp_client.py         # MCP client wrapper for HTTP calls
+-- real_mcp.py           # Real MCP server connections
+-- tools.py              # LangChain tool wrappers
+-- agents.py             # LangGraph agents (Pizza + Scheduling)
|
+-- main.py               # Main entry point
+-- run_agents.py         # Standalone agent runner
+-- terminal_ui.py        # Terminal UI with colors
+-- app.py                # Streamlit web UI
|
+-- requirements.txt      # Python dependencies
+-- .env.example          # Environment variable template
+-- orders/               # Order receipts (created at runtime)
```

### Module Descriptions

#### mock_api.py (Phase 0)

Purpose: Simulates the legacy pizza ordering REST API.

Endpoints:
- GET /menu - Returns all available pizzas
- GET /menu/{pizza_type} - Returns details for specific pizza
- POST /orders - Creates a new order
- GET /orders/{order_id} - Gets order status
- PATCH /orders/{order_id}/cancel - Cancels an order

Data Models:
- PizzaSize: Enum (small, medium, large)
- OrderRequest: pizza_type, size, quantity, notes
- OrderResponse: order_id, status, pizza_type, size, quantity, total_price, eta_minutes

Menu Items:
- margherita: $12.00
- pepperoni: $14.00
- quattro_formaggi: $16.00
- vegetarian: $13.00

#### generator.py (Phase 1)

Purpose: Converts OpenAPI specification to MCP server code.

Process:
1. Fetches OpenAPI spec from /openapi.json
2. Parses all paths, methods, and parameters
3. Resolves $ref references to component schemas
4. Generates Python functions with @mcp.tool decorators
5. Writes to generated_mcp_server.py

Key Functions:
- fetch_openapi_spec(url): Downloads OpenAPI JSON
- sanitize_function_name(name): Converts to valid Python identifier
- extract_parameters(operation, path): Gets path, query, body params
- resolve_schema_ref(spec, ref): Resolves $ref pointers
- generate_tool_function(): Creates individual tool code
- generate_mcp_server(): Produces complete server file

Generated Tools:
- get_menu_menu_get
- get_menu_item_menu__pizza_type__get
- create_order_orders_post
- get_order_orders__order_id__get
- cancel_order_orders__order_id__cancel_patch

#### mcp_client.py

Purpose: Provides HTTP-based MCP client for calling generated tools.

Classes:
- SimpleMCPClient: Wraps HTTP calls to look like MCP tool calls
  - connect(): Fetches OpenAPI spec, builds tool list
  - call_tool(name, arguments): Makes HTTP request
  - list_tools(): Returns available tools

#### real_mcp.py

Purpose: Connects to real external MCP servers via stdio transport.

Key Functions:
- get_npx_command(): Finds correct npx path on Windows/Linux

Classes:

1. RealMCPClient
   - Manages subprocess communication with MCP servers
   - Sends JSON-RPC requests over stdin/stdout
   - Handles Windows-specific subprocess settings
   - Methods: connect(), _send_request(), call_tool(), list_tools()

2. FilesystemMCPServer
   - Wrapper for @modelcontextprotocol/server-filesystem
   - Methods: write_file(), read_file(), list_directory()

3. MemoryMCPServer
   - Wrapper for @modelcontextprotocol/server-memory
   - Methods: create_entities(), create_relations(), search_nodes(), read_graph()

4. GoogleCalendarMCPServer
   - Wrapper for @cocal/google-calendar-mcp
   - Requires GOOGLE_OAUTH_CREDENTIALS environment variable
   - Methods: list_events(), create_event(), get_freebusy()

5. ExternalMCPManager
   - Orchestrates all external MCP connections
   - Methods: connect(), save_order_receipt(), store_order_in_memory(), 
     create_calendar_event(), schedule_delivery()

#### tools.py

Purpose: Bridges MCP tools to LangChain's tool interface.

Functions:
- create_langchain_tool_from_mcp(): Converts MCP tool definition to LangChain BaseTool

Classes:

1. PizzaMCPTools
   - Wraps generated MCP server tools for LangChain
   - Methods: initialize(), get_tools()

2. SchedulingTools
   - Provides external MCP tools for scheduling agent
   - Tools: schedule_delivery, create_calendar_event, save_order_receipt,
     get_order_history, send_notification

#### agents.py

Purpose: Implements LangGraph multi-agent workflow.

Classes:

1. AgentState (TypedDict)
   - messages: Conversation history
   - order_info: Order details (passed between agents)
   - current_agent: Active agent name
   - completed: Workflow completion flag

2. PizzaAgent
   - Uses Groq LLM (llama-3.3-70b-versatile)
   - Binds generated MCP tools
   - Processes natural language orders
   - Extracts order_info from responses

3. SchedulingAgent
   - Uses same LLM with scheduling tools
   - Receives order_info from Pizza Agent
   - Calls external MCP servers
   - Sends notifications

Functions:
- get_llm(): Initializes ChatGroq with API key
- build_workflow(): Creates LangGraph state machine
- run_conversation(): Executes workflow with user input

Workflow Graph:
```
Entry --> pizza_node --> [if order_placed] --> scheduling_node --> END
                     --> [else] --> END
```

#### main.py

Purpose: Main entry point that orchestrates all phases.

Functions:
- wait_for_api(): Polls API until ready (30 second timeout)
- start_mock_api(): Starts FastAPI subprocess
- run_generator(): Executes OpenAPI to MCP conversion
- run_agents(): Interactive agent loop

Flow:
1. Start mock API
2. Wait for API to be ready
3. Run generator
4. Initialize agents
5. Enter interactive loop

---

## MCP Server Integration

### Official MCP Servers Used

#### 1. Filesystem MCP Server

Package: @modelcontextprotocol/server-filesystem
Source: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

Purpose: Stores order receipts as JSON files

Connection Command:
```
npx -y @modelcontextprotocol/server-filesystem ./orders
```

Tools Available:
- read_file: Read file contents
- write_file: Write content to file
- list_directory: List directory contents
- create_directory: Create new directory
- move_file: Move or rename file
- search_files: Search for files
- get_file_info: Get file metadata

Usage in Project:
- Saves order receipts to ./orders/order_{id}.json
- Each receipt contains order details and timestamp

#### 2. Memory MCP Server

Package: @modelcontextprotocol/server-memory
Source: https://github.com/modelcontextprotocol/servers/tree/main/src/memory

Purpose: Knowledge graph for order history

Connection Command:
```
npx -y @modelcontextprotocol/server-memory
```

Tools Available:
- create_entities: Create nodes in graph
- create_relations: Create edges between nodes
- add_observations: Add facts to entities
- delete_entities: Remove nodes
- delete_observations: Remove facts
- delete_relations: Remove edges
- read_graph: Get entire graph
- search_nodes: Query nodes
- open_nodes: Get specific nodes

Usage in Project:
- Creates PizzaOrder entities for each order
- Stores observations: pizza type, size, price, ETA, status
- Enables order history queries

#### 3. Google Calendar MCP Server

Package: @cocal/google-calendar-mcp
Source: https://github.com/nspady/google-calendar-mcp

Purpose: Creates delivery events in Google Calendar

Connection Command:
```
npx -y @cocal/google-calendar-mcp
```

Tools Available:
- list-calendars: Get all calendars
- list-events: Get calendar events
- search-events: Search for events
- get-event: Get specific event
- list-colors: Get available colors
- create-event: Create new event
- update-event: Modify event
- delete-event: Remove event
- get-freebusy: Check availability
- get-current-time: Get current time
- respond-to-event: RSVP to event
- manage-accounts: Manage Google accounts

Usage in Project:
- Creates delivery event with:
  - calendarId: "primary"
  - summary: "Pizza Delivery - {type}"
  - description: Order details
  - start/end: Based on ETA

---

## Setup Instructions

### Prerequisites

1. Python 3.10 or higher
2. Node.js 18 or higher (for MCP servers)
3. Groq API key (free at https://console.groq.com)
4. Google Cloud Project (for Calendar integration)

### Step 1: Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Node.js Verification

```bash
# Check Node.js version
node --version   # Should be 18+

# Check npm/npx
npm --version
npx --version
```

Windows PowerShell Note:
If you get execution policy errors, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 3: Groq API Key

1. Go to https://console.groq.com
2. Sign up or log in
3. Go to API Keys section
4. Create new key (starts with gsk_)
5. Create .env file:

```
GROQ_API_KEY=gsk_your_key_here
```

### Step 4: Google Calendar Setup (Optional)

#### 4.1 Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Click "Select Project" then "New Project"
3. Name: "mission-pizza"
4. Click "Create"

#### 4.2 Enable Google Calendar API

1. Go to "APIs and Services" then "Library"
2. Search "Google Calendar API"
3. Click on it, then click "Enable"

#### 4.3 Create OAuth Credentials

1. Go to "APIs and Services" then "Credentials"
2. Click "Create Credentials" then "OAuth client ID"
3. If prompted, configure consent screen:
   - User Type: External
   - App name: Mission Pizza
   - User support email: your email
   - Developer email: your email
   - Click "Save and Continue"
   - Skip scopes
   - Add test user: your Gmail address
   - Click "Save"
4. Back to Credentials, create OAuth client ID:
   - Application type: Desktop app
   - Name: Mission Pizza Client
5. Click "Create"
6. Click "Download JSON"
7. Save as gcp-oauth.keys.json in project folder

#### 4.4 Set Environment Variable

Windows PowerShell:
```powershell
$env:GOOGLE_OAUTH_CREDENTIALS = "C:\path\to\gcp-oauth.keys.json"
```

Linux/Mac:
```bash
export GOOGLE_OAUTH_CREDENTIALS="/path/to/gcp-oauth.keys.json"
```

#### 4.5 Authenticate

```bash
npx -y @cocal/google-calendar-mcp auth
```

Browser opens for Google login. After authorization, tokens are saved.

### Step 5: Run Application

```bash
python main.py
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| GROQ_API_KEY | Yes | Groq API key for LLM |
| GOOGLE_OAUTH_CREDENTIALS | No | Path to Google OAuth JSON file |

### .env File Example

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_OAUTH_CREDENTIALS=C:\Users\admin\mission-pizza\gcp-oauth.keys.json
```

### API Configuration

The mock API runs on:
- Host: localhost
- Port: 8000
- Base URL: http://localhost:8000

### MCP Server Paths

On Windows, npx is located at:
```
C:\Program Files\nodejs\npx.cmd
```

The code automatically detects this path using shutil.which().

---

## Troubleshooting

### Problem: npm/npx not recognized in PowerShell

Error:
```
npm.ps1 cannot be loaded. The file is not digitally signed.
```

Solution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: API not starting

Error:
```
Connection refused on localhost:8000
```

Solution:
- Check if another process uses port 8000
- Run mock_api.py directly to see errors:
```bash
python mock_api.py
```

### Problem: MCP servers not connecting

Error:
```
Could not start filesystem. Is Node.js/npx installed?
```

Solution:
1. Verify Node.js installation:
```bash
node --version
```

2. Test MCP server directly:
```bash
npx -y @modelcontextprotocol/server-memory
```

### Problem: Groq model decommissioned

Error:
```
The model llama-3.1-70b-versatile has been decommissioned
```

Solution:
Edit agents.py line 36, change:
```python
model="llama-3.1-70b-versatile"
```
to:
```python
model="llama-3.3-70b-versatile"
```

### Problem: Google Calendar 403 access_denied

Error:
```
Error 403: access_denied
```

Solution:
1. Go to Google Cloud Console
2. Go to "APIs and Services" then "OAuth consent screen"
3. Add your email as a test user
4. Re-run authentication

### Problem: Google Calendar API not enabled

Error:
```
Google Calendar API has not been used in project... Enable it by visiting...
```

Solution:
1. Click the URL in the error message
2. Click "Enable" button
3. Wait 1-2 minutes
4. Try again

### Problem: Calendar event not created (calendarId error)

Error:
```
Invalid arguments for tool create-event: calendarId Required
```

Solution:
Ensure create-event call includes calendarId parameter:
```python
await self.calendar.client.call_tool("create-event", {
    "calendarId": "primary",  # This line is required
    "summary": "...",
    ...
})
```

### Problem: Character encoding error on Windows

Error:
```
'charmap' codec can't decode byte 0x8d
```

Note: This is a display error only. The API call usually succeeds. Check your Google Calendar to verify the event was created.

---

## Technical Decisions

### Why LangGraph for Agent Orchestration

- Built-in state management enables clean agent-to-agent communication
- Graph-based workflow allows conditional routing
- Native async support for concurrent operations
- Easy to extend with additional agents

### Why Groq as LLM Provider

- Fast inference times (important for interactive ordering)
- Good tool-calling support with function definitions
- Free tier available for development
- Official LangChain integration

### Why SimpleMCPClient over Full MCP Protocol

- More reliable on Windows systems
- Easier to debug HTTP calls
- Same end result (REST API calls)
- Can be swapped for full MCP client in production

### Why Subprocess for External MCP Servers

- Official MCP servers use stdio transport
- Subprocess allows proper stdin/stdout communication
- Matches how Claude Desktop connects to MCP servers
- Production-ready approach

### Why Fallback Mechanisms

- External MCP servers may not be available
- Graceful degradation maintains functionality
- Filesystem writes work without MCP
- Calendar shows simulated events if not configured

---

## Problems Faced and Solutions

### 1. Windows Subprocess Issues

Problem: Python subprocess could not find npx on Windows.

Root Cause: Windows uses npx.cmd, and the PATH lookup differs from Linux.

Solution: Created get_npx_command() function that:
- Uses shutil.which() to find npx.cmd
- Falls back to common installation paths
- Returns full path to executable

Code:
```python
def get_npx_command():
    if sys.platform == "win32":
        npx_cmd = shutil.which("npx.cmd") or shutil.which("npx")
        if npx_cmd:
            return npx_cmd
    return "npx"
```

### 2. PowerShell Execution Policy

Problem: npm and npx scripts blocked by PowerShell security.

Error: "File cannot be loaded. The file is not digitally signed."

Solution: Users must run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. API Startup Timing

Problem: Generator ran before API was ready, causing connection refused.

Root Cause: Simple time.sleep(2) was insufficient on Windows.

Solution: Implemented polling loop with 30-second timeout:
```python
def wait_for_api(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{url}/menu", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False
```

### 4. Groq Model Deprecation

Problem: llama-3.1-70b-versatile was decommissioned.

Solution: Updated to llama-3.3-70b-versatile in agents.py.

### 5. Google Calendar Authentication

Problem: 403 access_denied during OAuth flow.

Root Cause: Google Cloud app in "Testing" mode requires explicit test users.

Solution: Document requirement to add email as test user in OAuth consent screen.

### 6. Google Calendar API Not Enabled

Problem: API calls failed with "API not enabled" error.

Solution: Added step to enable Google Calendar API in Cloud Console before authentication.

### 7. Missing calendarId Parameter

Problem: create-event failed with validation error.

Root Cause: Google Calendar MCP requires calendarId parameter.

Solution: Added "calendarId": "primary" to all create-event calls.

### 8. Environment Variable Passing

Problem: Google Calendar MCP could not find credentials when spawned as subprocess.

Root Cause: Subprocess did not inherit custom environment variables.

Solution: Modified RealMCPClient to accept custom env dict:
```python
self.env = None  # Custom environment

# In connect():
process_env = self.env if self.env else os.environ.copy()
self.process = subprocess.Popen(..., env=process_env)
```

### 9. Character Encoding on Windows

Problem: Response from MCP server caused codec error.

Root Cause: Windows console uses different encoding than UTF-8.

Impact: Display error only; API calls succeed.

Workaround: Check Google Calendar directly to verify event creation.

---

## Requirements Summary

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Phase 1: OpenAPI to MCP | Complete | generator.py |
| Phase 2: Pizza Agent | Complete | agents.py PizzaAgent |
| Phase 3: Scheduling Agent | Complete | agents.py SchedulingAgent |
| External MCP Server | Complete | 3 servers connected |
| A2A Communication | Complete | LangGraph shared state |
| Google Calendar | Complete | Real event creation |

---
