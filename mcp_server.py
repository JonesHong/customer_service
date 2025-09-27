
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
    # QA functions
    first_visit,
    alishan_ticket,
    train_station_location,
    local_food,
    thank_you,
    opening_greeting,
    general_help,
    goodbye,
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

# === 嘉義旅遊 QA 工具 ===

@mcp.tool
def qa_first_visit() -> str:
    """
    回答：這是我第一次來嘉義，可以告訴我有什麼特別值得看的嗎？
    """
    return first_visit()

@mcp.tool
def qa_alishan_ticket() -> str:
    """
    回答：阿里山森林鐵路聽起來好棒！我要怎麼買票呢？
    """
    return alishan_ticket()

@mcp.tool
def qa_train_station_location() -> str:
    """
    回答：搭去阿里山的火車站就在附近嗎？
    """
    return train_station_location()

@mcp.tool
def qa_local_food() -> str:
    """
    回答：我在哪裡可以嘗到在地的美食呢？
    """
    return local_food()

@mcp.tool
def qa_thank_you() -> str:
    """
    回答：謝謝你！
    """
    return thank_you()

@mcp.tool
def qa_opening_greeting() -> str:
    """
    開場問候語
    """
    return opening_greeting()

@mcp.tool
def qa_general_help() -> str:
    """
    提供一般協助選項
    """
    return general_help()

@mcp.tool
def qa_goodbye() -> str:
    """
    道別語
    """
    return goodbye()



if __name__ == "__main__":
    # 預設以 stdio 執行；若要走 HTTP/SSE，請見 FastMCP 與 MCP SDK 文件
    # 開發期間可直接： python mcp_server.py

    # 選項 1: 使用 stdio 傳輸（本地進程）
    # mcp.run(transport="stdio")

    # 選項 2: 使用 SSE 傳輸（HTTP Server-Sent Events）
    mcp.run(transport="sse", host="127.0.0.1", port=9000)
