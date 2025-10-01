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
from services.qa import find_answer, get_qa_service

# 獲取日誌器（不重新配置 basicConfig，避免重複輸出）
tools_logger = logging.getLogger("core.tools")

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

# === 嘉義旅遊 QA 工具 (新系統) ===

@function_tool()
async def qa_find_answer(
    context: RunContext,  # type: ignore
    question: str
) -> str:
    """
    智慧問答系統 - 根據問題找出最相關的答案
    支援精確匹配、部分匹配和標籤匹配
    """
    return find_answer(question)

@function_tool()
async def qa_search_by_tag(
    context: RunContext,  # type: ignore
    tag: str
) -> str:
    """
    根據標籤搜尋相關問題
    可用標籤：阿里山、日出、美食、購票、交通、景點推薦、新手指南、在地美食
    """
    service = get_qa_service()
    questions = service.get_questions_by_tag(tag)
    if not questions:
        return f"沒有找到標籤 '{tag}' 相關的問題"

    result = f"標籤 '{tag}' 相關問題：\n"
    for q in questions:
        result += f"- {q['content']}\n"
    return result

@function_tool()
async def qa_list_tags(
    context: RunContext  # type: ignore
) -> str:
    """
    列出所有可用的標籤及使用次數
    """
    service = get_qa_service()
    tags = service.get_all_tags()
    if not tags:
        return "尚無標籤資料"

    result = "可用標籤列表：\n"
    for tag_name, count in tags:
        result += f"- {tag_name} ({count} 個相關內容)\n"
    return result

@function_tool()
async def qa_search_questions(
    context: RunContext,  # type: ignore
    keyword: str
) -> str:
    """
    搜尋包含關鍵字的問題
    """
    service = get_qa_service()
    questions = service.search_questions(keyword)
    if not questions:
        return f"沒有找到包含 '{keyword}' 的問題"

    result = f"包含 '{keyword}' 的問題：\n"
    for q in questions:
        tags = ', '.join(q['tags']) if q['tags'] else '無標籤'
        result += f"- {q['content']} [標籤: {tags}]\n"
    return result
