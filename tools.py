"""
LiveKit 工具模組 - 使用 LiveKit 框架提供工具服務
透過裝飾器包裝核心服務模組的無狀態函數
"""

import logging
from livekit.agents import function_tool, RunContext

# 引入服務模組
from services import (
    fetch_weather,
    search_web_ddg
)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s %(name)s - %(message)s",
)

# === LiveKit 工具定義 - 使用裝飾器包裝核心函數 ===

@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str
) -> str:
    """
    Get the current weather for a given city.
    """
    # 直接調用核心服務模組的無狀態函數
    return fetch_weather(city, timeout=2.0)

@function_tool()
async def search_web(
    context: RunContext,  # type: ignore
    query: str
) -> str:
    """
    Search the web using DuckDuckGo.
    """
    # 直接調用核心服務模組的無狀態函數
    return search_web_ddg(query, max_results=5)
