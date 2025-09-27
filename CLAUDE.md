# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chiayi customer service chatbot system using LiveKit agents with MCP (Model Context Protocol) integration. The system implements a voice-enabled AI assistant called "Friday" that can answer questions about Chiayi tourism and provide weather information.

## Core Architecture

### Service Components

1. **LiveKit Agent System** (`agent_tool.py`, `agent_mcp.py`)
   - Real-time voice agent using LiveKit's infrastructure
   - Supports both OpenAI and Google real-time models
   - Implements noise cancellation and video capabilities

2. **MCP Server** (`mcp_server.py`)
   - FastMCP-based server running on port 9000 (SSE transport)
   - Integrates with Qdrant vector database for document search
   - Provides weather and web search capabilities

3. **Qdrant Vector Database**
   - Hybrid search with dense and sparse vectors
   - Collection: `docs_hybrid`
   - Models: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (dense), `Qdrant/bm25` (sparse)
   - Running on `http://localhost:6333`

### Key Integration Points

- **MCP Client-Server Communication**: Agent connects to MCP server via HTTP/SSE at `http://localhost:9000/sse`
- **Tool Registration**: Tools are exposed via FastMCP decorators and automatically discovered by LiveKit agents
- **Prompts**: Character personality and instructions defined in `prompts.py`

## Development Commands

### Starting Services

```bash
# Start MCP server (required for agent_mcp.py)
python mcp_server.py

# Run LiveKit agent with direct tools
python agent_tool.py dev

# Run LiveKit agent with MCP integration
python agent_mcp.py dev
```

### Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate environment
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

## Environment Configuration

Required `.env` variables:
- `LIVEKIT_URL`: LiveKit server WebSocket URL
- `LIVEKIT_API_KEY`: LiveKit API key
- `LIVEKIT_API_SECRET`: LiveKit API secret
- `GOOGLE_API_KEY`: Google API key (for Google real-time model)

## Code Patterns

### Adding New Tools

Tools follow LiveKit's function tool pattern:
```python
@function_tool()
async def tool_name(context: RunContext, param: str) -> str:
    # Implementation
```

For MCP server tools:
```python
@mcp.tool
def tool_name(param: str) -> str:
    # Implementation
```

### Agent Configuration

Agents can use either direct tool integration or MCP servers:
- Direct: Pass tools list to Agent constructor
- MCP: Pass mcp_servers list with MCPServerHTTP instances

## Key Technical Details

- **Synonym Mapping**: The system includes Chinese-English synonym mappings for better search results (see `SYN_MAP` in `mcp_server.py`)
- **Retry Logic**: HTTP requests include retry strategies with exponential backoff
- **Error Handling**: All tools include try-except blocks with fallback messages
- **Logging**: Configured at INFO level with specific logger instances for different components