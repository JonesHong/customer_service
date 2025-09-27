
import logging

from utils.http_client import create_http_session


# 設定日誌
search_logger = logging.getLogger("core.search")


def search_web_ddg(query: str, max_results: int = 5, timeout: float = 3.0) -> str:
    """
    使用 DuckDuckGo 搜尋網路 (無狀態函數)

    優先使用 Instant Answer API，若無結果則使用 LangChain 的 DuckDuckGoSearchRun

    Args:
        query: 搜尋查詢字串
        max_results: 最大結果數量
        timeout: 請求超時時間（秒）

    Returns:
        搜尋結果字串或錯誤訊息
    """
    query = (query or "").strip()
    if not query:
        return "請提供查詢關鍵字。"

    session = create_http_session()

    # 嘗試 1：DDG Instant Answer API
    try:
        ia_url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "t": "friday-mcp"
        }
        response = session.get(ia_url, params=params, timeout=timeout)

        if response.ok:
            data = response.json()
            parts = []

            # 收集抽象文字和標題
            if data.get("AbstractText"):
                parts.append(data["AbstractText"])
            if data.get("Heading") and data["Heading"] not in parts:
                parts.append(data["Heading"])

            # 收集相關主題
            related = []
            for item in data.get("RelatedTopics", [])[:3]:
                if isinstance(item, dict):
                    if "Text" in item and item["Text"]:
                        related.append(item["Text"])
                    elif "Topics" in item and item["Topics"]:
                        topic_text = item["Topics"][0].get("Text", "")
                        if topic_text:
                            related.append(topic_text)

            if related:
                parts.append("；相關：" + " / ".join(related[:2]))

            if parts:
                result_text = " ".join(p for p in parts if p).strip()
                result_text = (result_text[:600] + "…") if len(result_text) > 600 else result_text
                search_logger.info(f"Search(IA) '{query}' -> {result_text[:100]}...")
                return result_text
    except Exception as e:
        search_logger.exception(f"DDG Instant Answer error for '{query}': {e}")

    # 嘗試 2：LangChain 的 DuckDuckGoSearchRun
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        # 嘗試使用新版參數，若不支援則降級
        try:
            tool = DuckDuckGoSearchRun(
                region="tw-tw",
                source="text",
                backend="api",
                max_results=max_results
            )
        except TypeError:
            # 舊版沒有 backend 參數
            tool = DuckDuckGoSearchRun(region="tw-tw", source="text")

        result = (tool.run(tool_input=query) or "").strip()
        result = (result[:800] + "…") if len(result) > 800 else result
        search_logger.info(f"Search(DDG) '{query}' -> {result[:100]}...")
        return result or f"沒有找到與「{query}」相關的明確結果。"
    except Exception as e:
        search_logger.exception(f"DuckDuckGoSearchRun error for '{query}': {e}")
        return f"搜尋「{query}」時發生連線或服務錯誤，請稍後再試。"


