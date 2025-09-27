# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chiayi customer service chatbot system using LiveKit real-time voice agents with MCP (Model Context Protocol) integration. The system implements a voice assistant called "Friday" that answers questions about Chiayi tourism and provides weather information.

## Core Architecture

### Modular Structure

The codebase follows a modular architecture with clear separation of concerns:

```
services/        # Business logic services (weather, web search)
utils/           # HTTP utilities and shared tools
config/          # System configuration and synonym mappings (if exists)
mcp_server.py    # FastMCP server exposing services as MCP tools
agent.py         # LiveKit voice agent connecting to MCP server
tools.py         # Direct LiveKit tool implementations (alternative to MCP)
prompts.py       # Agent personality and instructions
```

### Service Integration Flow

1. **MCP Server** (`mcp_server.py`) runs on `http://localhost:9000/sse`
   - Wraps services from `services/` module with `@mcp.tool` decorators
   - Exposes tools via FastMCP framework using SSE transport

2. **LiveKit Agent** (`agent.py`)
   - Connects to MCP server via `MCPServerHTTP` client
   - Uses OpenAI or Google real-time models for voice interaction
   - Can alternatively use direct tools from `tools.py`

3. **Service Modules** (`services/`)
   - Stateless pure functions for business logic
   - `weather.py`: Weather fetching via wttr.in API
   - `web_search.py`: DuckDuckGo search integration

## Development Commands

### Running the System

```bash
# Start MCP server first (required for agent.py)
python mcp_server.py

# In another terminal, run the LiveKit agent
python agent.py dev

# Alternative: Run with direct tools (no MCP server needed)
python tools.py dev
```

### Environment Setup

```bash
# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Testing Services

```bash
# Test individual service modules
python -c "from services import fetch_weather; print(fetch_weather('Taipei'))"

# Test MCP server endpoints
curl http://localhost:9000/sse
```

## Environment Configuration

Required `.env` file:
- `LIVEKIT_URL`: LiveKit server WebSocket URL
- `LIVEKIT_API_KEY`: LiveKit API key
- `LIVEKIT_API_SECRET`: LiveKit API secret
- `GOOGLE_API_KEY`: For Google real-time voice model (optional)

## Code Patterns

### Adding New MCP Tools

In `mcp_server.py`:
```python
@mcp.tool
def tool_name(param: str) -> str:
    return service_function(param)
```

### Adding New Services

1. Create function in `services/` module
2. Import in `services/__init__.py`
3. Wrap with decorator in `mcp_server.py` or `tools.py`

### LiveKit Direct Tools

In `tools.py`:
```python
@function_tool()
async def tool_name(context: RunContext, param: str) -> str:
    return service_function(param)
```

## Key Technical Details

- **Retry Logic**: HTTP requests use exponential backoff via `utils.http_client`
- **Synonym Mapping**: Chinese-English mappings for better search (if config exists)
- **Transport Options**: MCP supports stdio, SSE, or HTTP transport modes
- **Voice Models**: Supports both OpenAI and Google real-time models
- **Service Isolation**: Business logic separated from framework decorators