好的！下面把「用 Python + SQLite（含 FTS5）打造本地 QA＋多標籤系統」整理成一份**技術方案／落地指南**。內容涵蓋：架構、資料模型、全文檢索設計、關鍵 SQL、Python 程式骨架、效能與維運守則、測試與上線檢查表。要點都有附上權威文件出處，便於之後查核或擴充。

---

# 目標與範疇

* **目的**：在單機環境，用最小依賴打造「問答（Q/A）＋多標籤（TAG）」系統，支援**多對多**關係與**關鍵字/布林/前綴/近鄰**等全文檢索。
* **核心選型**：SQLite（內建於 Python `sqlite3`）＋FTS5 全文索引（同進程、零伺服器、BM25 排名、NEAR/前綴/布林查詢）。 ([Python documentation][1])

---

# 系統架構（邏輯）

1. **關聯資料層**（Q、A、TAG 與多對多交叉表）
2. **檢索層**：FTS5 虛擬表做倒排索引

   * 模式：建議採 **external content**（外部內容表），把文字留在主表／視圖，FTS5 只存索引；以**觸發器**或程式碼同步。 ([sqlite.org][2])
3. **服務層（Python）**：提供 `create/update/upsert/search` API；啟用 FK 約束、WAL、必要 PRAGMA。 ([sqlite.org][3])

---

# 資料模型（SQL）

```sql
PRAGMA foreign_keys = ON;             -- 啟用外鍵檢查
-- 核心實體
CREATE TABLE question (
  id INTEGER PRIMARY KEY,
  body TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE answer (
  id INTEGER PRIMARY KEY,
  body TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE tag (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- 多對多關係（交叉表）
CREATE TABLE question_answer (
  question_id INTEGER NOT NULL,
  answer_id   INTEGER NOT NULL,
  PRIMARY KEY (question_id, answer_id),
  FOREIGN KEY (question_id) REFERENCES question(id) ON DELETE CASCADE,
  FOREIGN KEY (answer_id)   REFERENCES answer(id)   ON DELETE CASCADE
);
CREATE TABLE question_tag (
  question_id INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  PRIMARY KEY (question_id, tag_id),
  FOREIGN KEY (question_id) REFERENCES question(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id)      REFERENCES tag(id)      ON DELETE CASCADE
);
CREATE TABLE answer_tag (
  answer_id INTEGER NOT NULL,
  tag_id    INTEGER NOT NULL,
  PRIMARY KEY (answer_id, tag_id),
  FOREIGN KEY (answer_id) REFERENCES answer(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id)    REFERENCES tag(id)    ON DELETE CASCADE
);
```

> SQLite 需顯式 `PRAGMA foreign_keys=ON` 才會強制外鍵約束；這是官方行為。 ([sqlite.org][3])

---

# 全文索引（FTS5）設計

## 1) 以視圖彙總要索引的文字

```sql
-- 將「Q 內容、A 內容、Q 的 tag、A 的 tag」彙整為可索引的一段文字
CREATE VIEW qa_index_view AS
SELECT
  q.id AS rowid,              -- 對應 FTS5 的 content_rowid
  q.body || ' ' ||
  IFNULL(GROUP_CONCAT(DISTINCT tq.name, ' '), '') || ' ' ||
  IFNULL(GROUP_CONCAT(DISTINCT ta.name, ' '), '') || ' ' ||
  IFNULL(GROUP_CONCAT(DISTINCT a.body, ' '), '') AS text
FROM question q
LEFT JOIN question_answer qa ON qa.question_id = q.id
LEFT JOIN answer a          ON a.id = qa.answer_id
LEFT JOIN question_tag qt   ON qt.question_id = q.id
LEFT JOIN tag tq            ON tq.id = qt.tag_id
LEFT JOIN answer_tag atg    ON atg.answer_id = a.id
LEFT JOIN tag ta            ON ta.id = atg.tag_id
GROUP BY q.id;
```

## 2) 建立 FTS5（external content）

```sql
CREATE VIRTUAL TABLE qa_fts
USING fts5(text, content='qa_index_view', content_rowid='rowid');
```

* **查詢語法**：支援詞組 `"..."`、布林 `AND/OR/NOT`、前綴 `term*`、近鄰 `NEAR/k`、欄位過濾等。 ([sqlite.org][2])
* **排名**：可用 `bm25(qa_fts)`；FTS5 內建 BM25。 ([slingacademy.com][4])
* **重點片段**：可用 `highlight()` 或 `snippet()`。 ([slingacademy.com][5])

## 3) 同步策略

外部內容需要在底層資料異動時維護 FTS：

* 簡單作法：**在應用層重建/更新**（插入或修改後，針對該 `rowid` 執行 `insert`/`delete` 操作碼）。
* 嚴謹作法：**觸發器**自動同步（示例）：

```sql
CREATE TRIGGER trg_qa_after_insert_question
AFTER INSERT ON question BEGIN
  INSERT INTO qa_fts(qa_fts, rowid, text)
  VALUES ('insert', NEW.id, (SELECT text FROM qa_index_view WHERE rowid=NEW.id));
END;

CREATE TRIGGER trg_qa_after_update_question
AFTER UPDATE ON question BEGIN
  INSERT INTO qa_fts(qa_fts, rowid, text) VALUES ('delete', NEW.id, '');
  INSERT INTO qa_fts(qa_fts, rowid, text)
  VALUES ('insert', NEW.id, (SELECT text FROM qa_index_view WHERE rowid=NEW.id));
END;
```

> 官方文件對 external-content / contentless 的差異與行為有說明；這類設計常見於節省重複內容。 ([sqlite.org][2])

---

# 關鍵查詢範例

```sql
-- 1) 純關鍵字（詞組＋前綴＋近鄰），並依 BM25 排序（分數愈小愈相關）
SELECT rowid, highlight(qa_fts, 0, '[', ']') AS frag, bm25(qa_fts) AS score
FROM qa_fts
WHERE qa_fts MATCH '("向量 檢索" OR RAG) NEAR/5 pipeline*'
ORDER BY score;

-- 2) 關鍵字 + 必須含某個 tag（於關聯層過濾）
SELECT q.id, q.body, bm25(qa_fts) AS score
FROM qa_fts
JOIN question q ON q.id = qa_fts.rowid
JOIN question_tag qt ON qt.question_id = q.id
JOIN tag t ON t.id = qt.tag_id
WHERE qa_fts MATCH 'embedding*'
  AND t.name = 'NLP'
ORDER BY score;

-- 3) 權重調整（多欄位時可自定 rank；此處示意）
-- SELECT rowid, rank(matchinfo(qa_fts)) AS score FROM qa_fts WHERE qa_fts MATCH '...';
```

> FTS5 的 MATCH 語法（詞組、前綴、NEAR、布林）與排名機制參見官方說明。 ([sqlite.org][2])

---

# 寫入與去重（UPSERT）

為避免重複 tag 或重覆的 Q/A 關聯，建議用 **INSERT … ON CONFLICT DO UPDATE**。

```sql
-- 唯一 tag
INSERT INTO tag(name) VALUES (?) 
ON CONFLICT(name) DO NOTHING;

-- 問答關聯（唯一主鍵保證去重）
INSERT INTO question_answer(question_id, answer_id) VALUES (?, ?)
ON CONFLICT(question_id, answer_id) DO NOTHING;
```

> SQLite 原生支援 UPSERT 語法（ON CONFLICT），細節與衝突目標設定見官方語法。 ([sqlite.org][6])

---

# Python 服務骨架（`sqlite3`）

```python
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_conn(db_path="qa.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")      # 外鍵
    conn.execute("PRAGMA journal_mode = WAL;")     # 併發/寫入體驗
    conn.execute("PRAGMA synchronous = NORMAL;")   # 視需求調整
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def upsert_tag(conn, name:str) -> int:
    cur = conn.execute("INSERT INTO tag(name) VALUES (?) ON CONFLICT(name) DO NOTHING;", (name,))
    cur = conn.execute("SELECT id FROM tag WHERE name=?", (name,))
    return cur.fetchone()["id"]

def add_question(conn, body:str) -> int:
    cur = conn.execute("INSERT INTO question(body) VALUES (?)", (body,))
    return cur.lastrowid

def add_answer(conn, body:str) -> int:
    cur = conn.execute("INSERT INTO answer(body) VALUES (?)", (body,))
    return cur.lastrowid

def link_q_a(conn, qid:int, aid:int):
    conn.execute("""INSERT INTO question_answer(question_id, answer_id)
                    VALUES (?, ?) ON CONFLICT(question_id, answer_id) DO NOTHING;""", (qid, aid))

def link_q_tag(conn, qid:int, tag:str):
    tid = upsert_tag(conn, tag)
    conn.execute("""INSERT INTO question_tag(question_id, tag_id)
                    VALUES (?, ?) ON CONFLICT(question_id, tag_id) DO NOTHING;""", (qid, tid))

def fts_refresh_one(conn, qid:int):
    conn.execute("INSERT INTO qa_fts(qa_fts, rowid, text) VALUES ('delete', ?, '');", (qid,))
    conn.execute("""INSERT INTO qa_fts(qa_fts, rowid, text)
                    VALUES('insert', ?, (SELECT text FROM qa_index_view WHERE rowid=?));""", (qid, qid))

def search(conn, query:str, required_tag:str|None=None, limit:int=20):
    if required_tag:
        sql = """
        SELECT q.id, q.body, bm25(qa_fts) AS score,
               highlight(qa_fts, 0, '[', ']') AS frag
        FROM qa_fts
        JOIN question q ON q.id = qa_fts.rowid
        JOIN question_tag qt ON qt.question_id = q.id
        JOIN tag t ON t.id = qt.tag_id
        WHERE qa_fts MATCH ? AND t.name = ?
        ORDER BY score LIMIT ?;
        """
        args = (query, required_tag, limit)
    else:
        sql = """
        SELECT rowid AS qid, bm25(qa_fts) AS score,
               snippet(qa_fts, 0, '[', ']', '...', 8) AS frag
        FROM qa_fts
        WHERE qa_fts MATCH ?
        ORDER BY score LIMIT ?;
        """
        args = (query, limit)
    return conn.execute(sql, args).fetchall()
```

> `sqlite3` 是 Python 標準庫；以上示範的連線、交易、查詢都符合官方 API。WAL 與 PRAGMA 動作需在連線後設定。 ([Python documentation][1])
> WAL/同步等 PRAGMA 的行為與影響，見官方 WAL 說明與 PRAGMA 說明。 ([sqlite.org][7])
> `highlight()/snippet()` 與 BM25 排名在 FTS5 有內建支援。 ([slingacademy.com][5])

---

# 效能與維運守則

1. **WAL 模式**：更佳讀寫併發；在單機應用多用戶/多執行緒會更順。 ([sqlite.org][7])
2. **索引更新策略**：大量批次寫入時，可先關閉觸發器／延後 FTS 重建，再一次性 `rebuild`。
3. **交易包裝**：批量作業請用單一 `BEGIN … COMMIT` 減少 fsync 次數。
4. **外鍵與一致性**：務必 `PRAGMA foreign_keys=ON`；避免孤兒資料。 ([sqlite.org][3])
5. **UPSERT**：標籤與交叉表用 `ON CONFLICT DO NOTHING/UPDATE` 去重、對齊。 ([sqlite.org][6])
6. **搜尋體驗**：

   * 查詢語法活用 `"phrase"`, `term*`（前綴）, `NEAR/k`, `AND/OR/NOT`。 ([sqlite.org][2])
   * 排名採 `bm25()`；必要時以自訂 rank 函式權重欄位。 ([slingacademy.com][4])
   * 前端展示時用 `snippet()` 或 `highlight()` 標出關鍵詞。 ([slingacademy.com][5])

---

# 測試數據與驗收清單

* **功能**

  * 新增 Q、A、TAG；Q↔A、Q↔TAG、A↔TAG 關聯；重複寫入不報錯（UPSERT）。 ([sqlite.org][6])
  * 修改/刪除 Q 或 A 後，FTS 結果同步更新。
  * 以 `("向量 檢索" OR RAG) NEAR/5 pipeline*` 搜尋，順位合理。 ([sqlite.org][2])
* **非功能**

  * 1000～10萬級別文檔測試搜尋延時（p50/p95）。
  * 1寫多讀情境下 WAL 效果與鎖等待。 ([sqlite.org][7])
  * 備份：確保 `.db`、`-wal`、`-shm` 檔案的一致性（WAL 模式下）。 ([sqlite.org][7])

---

# 常見擴充

* **權重比**：將 Q 文字、A 文字、TAG 拆為多欄 FTS，再自訂 rank（給 Q 權重較高）。 ([slingacademy.com][4])
* **欄位過濾**：FTS5 支援「欄位：查詢」語法（在多欄索引時）。 ([sqlite.org][2])
* **片段摘要**：`snippet()` 限制片段長度與省略符，改善列表呈現。 ([Stack Overflow][8])

---

# 風險與注意

* **external content** 需要嚴謹維護（觸發器/程式同步）；否則索引與內容可能脫鉤。可視需要改「contentless」模式，但查詢取得原文時要自行回表。 ([sqlite.org][9])
* **PRAGMA 行為** 因版本／平台有差異，請以官方說明為準（journal\_mode、synchronous、foreign\_keys 等）。 ([sqlite.org][10])

---

# 參考資料（精選）

* **FTS5 官方文件**：語法（詞組/NEAR/前綴/布林）、建表、tokenizer、external-content。 ([sqlite.org][2])
* **Python `sqlite3` 官方文件**：連線、交易、cursor、row factory。 ([Python documentation][1])
* **UPSERT 語法**：`INSERT ... ON CONFLICT DO ...`。 ([sqlite.org][6])
* **WAL 與 PRAGMA**：效能與一致性考量。 ([sqlite.org][7])
* **BM25 與排名/高亮**：實作與示例。 ([slingacademy.com][4])

---

如果你想把這份指南**輸出成 Markdown/PDF** 方便存檔或分享，我可以直接幫你導出檔案版（含可執行的建表與 Python 範例段落）。

[1]: https://docs.python.org/3/library/sqlite3.html?utm_source=chatgpt.com "sqlite3 — DB-API 2.0 interface for SQLite databases - Python"
[2]: https://sqlite.org/fts5.html?utm_source=chatgpt.com "SQLite FTS5 Extension"
[3]: https://sqlite.org/foreignkeys.html?utm_source=chatgpt.com "SQLite Foreign Key Support"
[4]: https://www.slingacademy.com/article/ranking-full-text-search-results-in-sqlite-explained/?utm_source=chatgpt.com "Ranking Full-Text Search Results in SQLite Explained"
[5]: https://www.slingacademy.com/article/highlighting-search-terms-in-sqlite-full-text-queries/?utm_source=chatgpt.com "Highlighting Search Terms in SQLite Full-Text Queries"
[6]: https://sqlite.org/lang_upsert.html?utm_source=chatgpt.com "UPSERT - SQLite"
[7]: https://sqlite.org/wal.html?utm_source=chatgpt.com "Write-Ahead Logging"
[8]: https://stackoverflow.com/questions/72972435/how-do-i-use-the-snippet-function-using-a-fts5-virtual-table-in-sqlite?utm_source=chatgpt.com "How do I use the snippet () function using a FTS5 virtual table in SQLite? - Stack Overflow"
[9]: https://sqlite.org/forum/forumpost/44fe70950bd5bb1eb510c2558b03b3d05d870dee02384a9331890253c413ceef?utm_source=chatgpt.com "SQLite User Forum: Differences between FTS5 ’external content’ and ’contentless’ vTabs"
[10]: https://sqlite.org/pragma.html?utm_source=chatgpt.com "Pragma statements supported by SQLite"
