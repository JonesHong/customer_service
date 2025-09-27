"""
核心服務模組 - 提供無狀態的業務邏輯函數
這些函數可以被 MCP 伺服器和 LiveKit 代理重用
"""

import logging
import requests
from typing import Optional, Dict, List, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote
import textwrap

# 嘗試導入 Qdrant（可選依賴）
try:
    from qdrant_client import QdrantClient, models as qmodels
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    qmodels = None

# 設定日誌
weather_logger = logging.getLogger("core.weather")
search_logger = logging.getLogger("core.search")
search_docs_logger = logging.getLogger("core.search_docs")

# ========= Qdrant 配置 =========
QDRANT_CONFIG = {
    "url": "http://localhost:6333",
    "collection": "docs_hybrid",
    "dense_name": "dense",
    "sparse_name": "sparse",
    "dense_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sparse_model": "Qdrant/bm25"
}

# 同義詞映射表
SYNONYM_MAP = {
    "阿里山森林鐵路": ["阿里山小火車", "森林小火車", "Alishan Forest Railway", "Alishan train"],
    "阿里山": ["Alishan"],
    "嘉義火車站": ["嘉義車站", "Chiayi Station", "Chiayi Railway Station"],
    "文化路夜市": ["Wenhua Road Night Market", "文化夜市"],
    "檜意森活村": ["Hinoki Village", "Hinoki Cultural Village"],
    "北門驛": ["Beimen Station", "北門車站"],
    "火雞肉飯": ["turkey rice"],
    "砂鍋魚頭": ["fish head casserole"],
    "日出": ["sunrise"],
}


def create_http_session() -> requests.Session:
    """
    建立帶有重試機制的 HTTP Session

    Returns:
        設定好的 requests.Session 物件
    """
    retry = Retry(
        total=3,                # 最多重試 3 次
        backoff_factor=0.5,     # 0.5, 1.0, 2.0 秒遞增
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Friday-MCP/1.0 (+https://example.local)"
    })
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch_weather(city: str, timeout: float = 3.0) -> str:
    """
    取得指定城市的天氣資訊 (無狀態函數)

    Args:
        city: 城市名稱
        timeout: 請求超時時間（秒）

    Returns:
        天氣資訊字串或錯誤訊息
    """
    if not city or not city.strip():
        return "請提供城市名稱。"

    session = create_http_session()
    city_quoted = quote(city, safe="")

    # 主要使用 HTTPS，HTTP 作為備援
    urls = [
        f"https://wttr.in/{city_quoted}?format=3",
        f"http://wttr.in/{city_quoted}?format=3",  # 備援
    ]

    for url in urls:
        try:
            response = session.get(url, timeout=timeout)
            if response.ok and response.text.strip():
                weather_info = response.text.strip()
                weather_logger.info(f"Weather for {city}: {weather_info}")
                return weather_info
            else:
                weather_logger.warning(f"wttr.in bad response ({response.status_code}): {url}")
        except Exception as e:
            weather_logger.exception(f"Error retrieving weather for {city} via {url}: {e}")

    # 最終備援訊息
    return f"目前無法取得 {city} 的天氣（連線不穩或服務繁忙）。請稍後再試。"


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


def search_documents(
    query: str,
    qdrant_url: str = QDRANT_CONFIG["url"],
    collection_name: str = QDRANT_CONFIG["collection"],
    limit: int = 5
) -> str:
    """
    從 Qdrant 向量資料庫搜尋文件 (無狀態函數)

    Args:
        query: 搜尋查詢字串
        qdrant_url: Qdrant 伺服器 URL
        collection_name: 集合名稱
        limit: 返回結果數量限制

    Returns:
        格式化的搜尋結果或錯誤訊息
    """
    query = (query or "").strip()
    if not query:
        return "請提供查詢關鍵字。"

    # 檢查 Qdrant 是否可用
    if not QDRANT_AVAILABLE:
        return "Qdrant 向量資料庫未安裝或不可用。請安裝 qdrant-client: pip install qdrant-client"

    try:
        # 建立 Qdrant 客戶端連接
        client = QdrantClient(url=qdrant_url)

        # 執行混合搜尋
        results = client.query(
            collection_name=collection_name,
            query_text=query,
            limit=limit
        )

        if not results:
            return f"沒有找到與「{query}」相關的文件。"

        # 格式化結果
        formatted_results = []
        for i, result in enumerate(results, 1):
            score = result.score
            payload = result.payload or {}

            title = payload.get("title", "無標題")
            content = payload.get("content", "")
            source = payload.get("source", "")

            # 擷取內容摘要
            content_preview = textwrap.shorten(content, width=200, placeholder="...")

            formatted_results.append(
                f"{i}. [{title}] (相關度: {score:.2f})\n"
                f"   {content_preview}\n"
                f"   來源: {source if source else '未知'}"
            )

        result_text = "\n\n".join(formatted_results)
        search_docs_logger.info(f"Document search '{query}' returned {len(results)} results")
        return result_text

    except Exception as e:
        search_docs_logger.exception(f"Error searching documents for '{query}': {e}")
        return f"搜尋文件「{query}」時發生錯誤：{str(e)}"


def expand_query_with_synonyms(query: str, synonym_map: Dict[str, List[str]] = None) -> str:
    """
    使用同義詞擴展查詢字串 (無狀態函數)

    Args:
        query: 原始查詢字串
        synonym_map: 同義詞映射表，預設使用 SYNONYM_MAP

    Returns:
        擴展後的查詢字串
    """
    if synonym_map is None:
        synonym_map = SYNONYM_MAP

    expanded_terms = [query]

    # 檢查每個同義詞組
    for main_term, synonyms in synonym_map.items():
        # 如果查詢包含主要術語或任何同義詞
        if main_term.lower() in query.lower():
            expanded_terms.extend(synonyms)
        else:
            for synonym in synonyms:
                if synonym.lower() in query.lower():
                    expanded_terms.append(main_term)
                    expanded_terms.extend([s for s in synonyms if s != synonym])
                    break

    # 去除重複並組合
    unique_terms = list(dict.fromkeys(expanded_terms))
    return " OR ".join(unique_terms)


# 簡單的健康檢查函數
def health_check() -> Dict[str, str]:
    """
    系統健康檢查 (無狀態函數)

    Returns:
        包含各服務狀態的字典
    """
    status = {
        "status": "healthy",
        "services": {
            "weather": "unknown",
            "web_search": "unknown",
            "document_search": "unknown"
        }
    }

    # 測試天氣服務
    try:
        result = fetch_weather("Taipei", timeout=1.0)
        status["services"]["weather"] = "available" if "°" in result else "degraded"
    except:
        status["services"]["weather"] = "unavailable"

    # 測試 Qdrant
    if QDRANT_AVAILABLE:
        try:
            client = QdrantClient(url=QDRANT_CONFIG["url"], timeout=1.0)
            collections = client.get_collections()
            status["services"]["document_search"] = "available"
        except:
            status["services"]["document_search"] = "unavailable"
    else:
        status["services"]["document_search"] = "not_installed"

    # 檢查整體狀態
    if "unavailable" in status["services"].values():
        status["status"] = "degraded"

    return status