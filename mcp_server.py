
"""
MCP 伺服器 - 使用 FastMCP 框架提供工具服務
透過裝飾器包裝核心服務模組的無狀態函數
"""

import logging
from fastmcp import FastMCP

# 引入服務模組
from services import (
    fetch_weather,
    search_web_ddg,
)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s %(name)s - %(message)s",
)
logging.getLogger("ddgs.ddgs").setLevel(logging.ERROR)  # 降噪 DuckDuckGoSearch 的子引擎錯誤

# 初始化 MCP 伺服器
mcp = FastMCP("Friday MCP Server 🚀")

# === MCP 工具定義 - 使用裝飾器包裝核心函數 ===

@mcp.tool
def get_weather(city: str) -> str:
    """
    取得城市即時天氣（wttr.in）。內建 timeout/重試/編碼與備援。
    """
    return fetch_weather(city)

@mcp.tool
def search_web(query: str) -> str:
    """
    Web 搜尋（穩定版）：
    1) 先用 DuckDuckGo Instant Answer（快、JSON）
    2) 若無結果/出錯，退到 DuckDuckGoSearchRun
    """
    return search_web_ddg(query)



if __name__ == "__main__":
    # 預設以 stdio 執行；若要走 HTTP/SSE，請見 FastMCP 與 MCP SDK 文件
    # 開發期間可直接： python mcp_server.py

    # 選項 1: 使用 stdio 傳輸（本地進程）
    # mcp.run(transport="stdio")

    # 選項 2: 使用 SSE 傳輸（HTTP Server-Sent Events）
    mcp.run(transport="sse", host="127.0.0.1", port=9000)
