
import logging
from fastmcp import FastMCP
# from fastmcp import tools 
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote
from qdrant_client import QdrantClient, models as qmodels
import textwrap
# ========= Qdrant 基本設定 =========
QDRANT_URL = "http://localhost:6333"
COLLECTION  = "docs_hybrid"
DENSE_NAME  = "dense"
SPARSE_NAME = "sparse"

DENSE_MODEL  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SPARSE_MODEL = "Qdrant/bm25"   # 已在 collection 設定 Modifier.IDF

client = QdrantClient(url=QDRANT_URL)

# 和 ingest 同步的同義詞表
SYN_MAP = {
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


logging.getLogger("ddgs.ddgs").setLevel(logging.ERROR)  # 降噪 DuckDuckGoSearch 的子引擎錯誤
weather_logger = logging.getLogger("mcp.weather")
search_logger = logging.getLogger("mcp.search")
search_docs_logger = logging.getLogger("mcp.search_docs")
mcp = FastMCP("Friday MCP Server 🚀")

def _http_session():
    # 建立帶重試的 requests session
    retry = Retry(
        total=3,                # 最多重試 3 次
        backoff_factor=0.5,     # 0.5, 1.0, 2.0 秒遞增
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Friday-MCP/1.0 (+https://example.local)"
    })
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

@mcp.tool
def get_weather(city: str) -> str:
    """
    取得城市即時天氣（wttr.in）。內建 timeout/重試/編碼與備援。
    """
    sess = _http_session()
    city_q = quote(city, safe="")
    # 主要使用 HTTPS，並縮短格式，避免非 ASCII 造成奇怪編碼
    urls = [
        f"https://wttr.in/{city_q}?format=3",
        f"http://wttr.in/{city_q}?format=3",  # 備援：HTTP
    ]
    for url in urls:
        try:
            resp = sess.get(url, timeout=3.0)
            if resp.ok and resp.text.strip():
                text = resp.text.strip()
                weather_logger.info("Weather for %s: %s", city, text)
                return text
            else:
                weather_logger.warning("wttr.in bad response (%s): %s", resp.status_code, url)
        except Exception as e:
            weather_logger.exception("Error retrieving weather for %s via %s", city, url)
    # 最終備援：給個友善訊息
    return f"目前無法取得 {city} 的天氣（連線不穩或服務繁忙）。請稍後再試。"


# @mcp.tool
# def search_web(query: str) -> str:
#     """
#     Web 搜尋（穩定版）：
#     1) 先用 DuckDuckGo Instant Answer（快、JSON）
#     2) 若無結果/出錯，退到 DuckDuckGoSearchRun（強制 region，降噪 ddgs）
#     """
#     q = (query or "").strip()
#     if not q:
#         return "請提供查詢關鍵字。"

#     sess = _http_session()

#     # --- 嘗試 1：DDG Instant Answer API ---
#     try:
#         ia_url = "https://api.duckduckgo.com/"
#         params = {"q": q, "format": "json", "no_redirect": "1", "no_html": "1", "t": "friday-mcp"}
#         r = sess.get(ia_url, params=params, timeout=3.0)
#         if r.ok:
#             data = r.json()
#             parts = []
#             if data.get("AbstractText"):
#                 parts.append(data["AbstractText"])
#             if data.get("Heading") and data["Heading"] not in parts:
#                 parts.append(data["Heading"])

#             rel = []
#             for item in data.get("RelatedTopics", [])[:3]:
#                 if isinstance(item, dict):
#                     if "Text" in item and item["Text"]:
#                         rel.append(item["Text"])
#                     elif "Topics" in item and item["Topics"]:
#                         t0 = item["Topics"][0].get("Text", "")
#                         if t0:
#                             rel.append(t0)
#             if rel:
#                 parts.append("；相關：" + " / ".join(rel[:2]))

#             if parts:
#                 text = " ".join(p for p in parts if p).strip()
#                 text = (text[:600] + "…") if len(text) > 600 else text
#                 search_logger.info("Search(IA) '%s' -> %s", q, text)
#                 return text
#     except Exception:
#         search_logger.exception("DDG Instant Answer error for '%s'", q)

#     # --- 嘗試 2：LangChain 的 DuckDuckGoSearchRun（指定 region，避免奇怪子網域） ---
#     try:
#         from langchain_community.tools import DuckDuckGoSearchRun
#         # 說明：
#         # - region="tw-tw"：強制台灣區，ddgs 會對應正確語系，避免 wt.wikipedia.org 這類不存在子域
#         # - source="text"：一般網頁結果（非新聞）
#         # - backend="api"：偏好 API 模式（有些版本不支援，下面會 try/except）
#         try:
#             tool = DuckDuckGoSearchRun(region="tw-tw", source="text", backend="api", max_results=5)
#         except TypeError:
#             # 舊版沒有 backend 參數就降級
#             tool = DuckDuckGoSearchRun(region="tw-tw", source="text")

#         result = (tool.run(tool_input=q) or "").strip()
#         result = (result[:800] + "…") if len(result) > 800 else result
#         search_logger.info("Search(DDG) '%s' -> %s", q, result.replace("\n", " ")[:160])
#         return result or f"沒有找到與「{q}」相關的明確結果。"
#     except Exception:
#         search_logger.exception("DuckDuckGoSearchRun error for '%s'", q)
#         return f"搜尋「{q}」時發生連線或服務錯誤，請稍後再試。"



if __name__ == "__main__":
    # 預設以 stdio 執行；若要走 HTTP/SSE，請見 FastMCP 與 MCP SDK 文件。
    # 開發期間可直接： python mcp_server.py
    # mcp.run(transport="stdio")
    
    # mcp.port = 9000
    # mcp.run(transport="sse")   # 或 "http"
    mcp.run(transport="sse", host="127.0.0.1", port=9000)
