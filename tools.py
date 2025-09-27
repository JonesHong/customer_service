"""
LiveKit 工具模組 - 使用 LiveKit 框架提供工具服務
透過裝飾器包裝核心服務模組的無狀態函數
"""

import logging
from livekit.agents import function_tool, RunContext
from core_services import (
    fetch_weather,
    search_web_ddg,
    search_documents,
    expand_query_with_synonyms,
    QDRANT_CONFIG
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

@function_tool()
async def search_docs(
    context: RunContext,  # type: ignore
    query: str,
    limit: int = 5
) -> str:
    """
    Search documents from Qdrant vector database.
    """
    # 可選：使用同義詞擴展查詢
    expanded_query = expand_query_with_synonyms(query)

    # 調用核心服務模組的文件搜尋函數
    return search_documents(
        expanded_query,
        qdrant_url=QDRANT_CONFIG["url"],
        collection_name=QDRANT_CONFIG["collection"],
        limit=limit
    )

@function_tool()
async def get_weather_batch(
    context: RunContext,  # type: ignore
    cities: list
) -> dict:
    """
    Get weather for multiple cities at once.
    批次取得多個城市的天氣資訊
    """
    results = {}
    for city in cities:
        results[city] = fetch_weather(city, timeout=2.0)
    return results    
