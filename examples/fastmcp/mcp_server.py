# server.py
from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

"""
Tools
Tools allow LLMs to perform actions by executing your Python functions (sync or async). Ideal for computations, API calls, or side effects (like POST/PUT). FastMCP handles schema generation from type hints and docstrings. Tools can return various types, including text, JSON-serializable objects, and even images or audio aided by the FastMCP media helper classes.
"""
@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Static resource
"""
Resources & Templates
Resources expose read-only data sources (like GET requests). Use @mcp.resource("your://uri"). Use {placeholders} in the URI to create dynamic templates that accept parameters, allowing clients to request specific data subsets.
"""
@mcp.resource("config://version")
def get_version(): 
    return "2.0.1"

"""
Prompts
Prompts define reusable message templates to guide LLM interactions. Decorate functions with @mcp.prompt. Return strings or Message objects.
"""
@mcp.prompt
def summarize_request(text: str) -> str:
    """Generate a prompt asking for a summary."""
    return f"Please summarize the following text:\n\n{text}"

if __name__ == "__main__":
    mcp.run()
    
# fastmcp run server.py