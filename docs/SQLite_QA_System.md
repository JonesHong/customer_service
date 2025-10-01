# SQLite QA 系統文件

## 系統架構

本系統採用 SQLite3 資料庫管理問答內容，實現了 Q（問題）、A（答案）、Tags（標籤）的多對多關係架構。

### 資料庫結構

```sql
-- 問題表
questions (
    id INTEGER PRIMARY KEY,
    content TEXT UNIQUE,
    created_at TIMESTAMP
)

-- 答案表
answers (
    id INTEGER PRIMARY KEY,
    content TEXT UNIQUE,
    created_at TIMESTAMP
)

-- 標籤表
tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    created_at TIMESTAMP
)

-- 問題-答案關聯表（多對多）
question_answers (
    question_id INTEGER,
    answer_id INTEGER,
    priority INTEGER (0-100),
    PRIMARY KEY (question_id, answer_id)
)

-- 問題-標籤關聯表（多對多）
question_tags (
    question_id INTEGER,
    tag_id INTEGER
)

-- 答案-標籤關聯表（多對多）
answer_tags (
    answer_id INTEGER,
    tag_id INTEGER
)
```

## 核心功能

### 1. 資料遷移

從原有 JSON 檔案遷移到 SQLite：

```bash
python migrate_data.py
```

### 2. 問答查詢

系統支援三種查詢方式：
- **精確匹配**：完全匹配問題內容
- **部分匹配**：包含關鍵字的模糊匹配
- **標籤匹配**：基於標籤的智慧匹配

### 3. 標籤系統

自動產生的標籤類別：
- 阿里山
- 日出
- 美食
- 購票
- 交通
- 景點推薦
- 新手指南
- 在地美食

## 使用方式

### 執行測試

```bash
# 測試 QA 系統功能
python test_qa_system.py

# 啟動 MCP 伺服器
python mcp_server.py
```

### API 使用範例

```python
from services import get_qa_service

# 取得服務實例
service = get_qa_service()

# 查詢答案
answer = service.find_answer("第一次來嘉義")

# 根據標籤搜尋
questions = service.get_questions_by_tag("美食")

# 新增問答對
service.add_qa_pair(
    question="新問題",
    answer="新答案",
    tags=["標籤1", "標籤2"],
    priority=80
)
```

## MCP 工具

新增的 MCP 工具：
- `qa_find_answer(question)`：智慧問答查詢
- `qa_search_by_tag(tag)`：根據標籤搜尋問題
- `qa_list_tags()`：列出所有可用標籤
- `qa_search_questions(keyword)`：關鍵字搜尋問題

## 向後相容

系統保留了原有的函數介面，確保現有程式碼可以正常運作：
- `first_visit()`
- `alishan_ticket()`
- `train_station_location()`
- `local_food()`
- `thank_you()`

## MVP 原則實踐

1. **最小化功能**：只實現核心 CRUD 和查詢功能
2. **快速驗證**：提供測試腳本快速驗證功能
3. **漸進式開發**：保留向後相容，可逐步遷移
4. **簡單架構**：使用 SQLite 輕量級資料庫
5. **易於擴展**：多對多關係設計支援未來擴充