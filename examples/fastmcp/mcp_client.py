from fastmcp import Client

# Standard MCP configuration with multiple servers
config = {
    "mcpServers": {
        "weather": {"url": "https://weather-api.example.com/mcp"},
        "assistant": {"command": "python", "args": ["./assistant_server.py"]}
    }
}


# async def main():
#     # Connect via stdio to a local script
#     async with Client("my_server.py") as client:
#         tools = await client.list_tools()
#         print(f"Available tools: {tools}")
#         result = await client.call_tool("add", {"a": 5, "b": 3})
#         print(f"Result: {result.content[0].text}")

#     # Connect via SSE
#     async with Client("http://localhost:8000/sse") as client:
#         # ... use the client
#         pass

# Create a client that connects to all servers
client = Client(config)

async def main():
    async with client:
        # Access tools and resources with server prefixes
        forecast = await client.call_tool("weather_get_forecast", {"city": "London"})
        answer = await client.call_tool("assistant_answer_question", {"query": "What is MCP?"})