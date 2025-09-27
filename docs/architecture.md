# 系統架構 - 核心服務與裝飾器模式

## 架構概覽

本專案採用**核心服務 + 裝飾器**的設計模式，將業務邏輯與框架整合分離：

```
┌─────────────────────────────────────────────┐
│           core_services.py                  │
│     (無狀態業務邏輯函數 - Pure Functions)    │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐ ┌────────▼────────┐
│  mcp_server.py  │ │    tools.py     │
│  (@mcp.tool)    │ │ (@function_tool)│
└────────────────┘ └─────────────────┘
        │                   │
        │                   │
┌───────▼────────┐ ┌────────▼────────┐
│  MCP Client    │ │  LiveKit Agent  │
└────────────────┘ └─────────────────┘
```

## 模組說明

### 1. 核心服務模組 (`core_services.py`)

提供**無狀態的純函數**，包含所有業務邏輯：

- `fetch_weather()` - 取得天氣資訊
- `search_web_ddg()` - DuckDuckGo 網頁搜尋
- `search_documents()` - Qdrant 向量資料庫搜尋
- `expand_query_with_synonyms()` - 同義詞查詢擴展
- `health_check()` - 系統健康檢查

**特點：**
- 無狀態設計，可重用性高
- 與框架無關，易於測試
- 統一的錯誤處理和日誌記錄

### 2. MCP 伺服器 (`mcp_server.py`)

使用 FastMCP 框架，透過裝飾器包裝核心函數：

```python
@mcp.tool
def get_weather(city: str) -> str:
    return fetch_weather(city)
```

**運行方式：**
```bash
python mcp_server.py  # 預設 SSE 傳輸，port 9000
```

### 3. LiveKit 工具 (`tools.py`)

使用 LiveKit agents 框架，透過裝飾器包裝核心函數：

```python
@function_tool()
async def get_weather(context: RunContext, city: str) -> str:
    return fetch_weather(city)
```

**整合方式：**
- 直接引入到 `agent_tool.py` 使用
- 或透過 MCP 伺服器在 `agent_mcp.py` 使用

## 優點

1. **程式碼重用** - 業務邏輯只需撰寫一次
2. **易於維護** - 修改核心邏輯自動影響所有使用處
3. **框架無關** - 可輕易支援新框架（只需加裝飾器）
4. **測試友好** - 純函數易於單元測試
5. **關注點分離** - 業務邏輯與框架整合分離

## 新增功能範例

若要新增一個翻譯功能：

### 步驟 1: 在 `core_services.py` 新增核心函數

```python
def translate_text(text: str, target_lang: str = "en") -> str:
    """翻譯文字到指定語言"""
    # 實作翻譯邏輯
    return translated_text
```

### 步驟 2: 在 `mcp_server.py` 加入 MCP 工具

```python
@mcp.tool
def translate(text: str, target_lang: str = "en") -> str:
    """翻譯文字"""
    return translate_text(text, target_lang)
```

### 步驟 3: 在 `tools.py` 加入 LiveKit 工具

```python
@function_tool()
async def translate(
    context: RunContext,
    text: str,
    target_lang: str = "en"
) -> str:
    """翻譯文字"""
    return translate_text(text, target_lang)
```

## 測試

執行測試腳本驗證所有模組：

```bash
python test_refactoring.py
```

測試涵蓋：
- 核心服務函數
- MCP 伺服器工具
- LiveKit 工具
- 批次操作

## 配置管理

核心配置集中在 `core_services.py`：

```python
QDRANT_CONFIG = {
    "url": "http://localhost:6333",
    "collection": "docs_hybrid",
    # ...
}

SYNONYM_MAP = {
    # 同義詞對應表
}
```

## 擴展性

此架構支援：
- 新增更多框架整合（如 FastAPI、Flask）
- 支援不同的 MCP 傳輸協定（stdio、SSE、WebSocket）
- 整合更多外部服務（資料庫、API）
- 水平擴展（多實例部署）