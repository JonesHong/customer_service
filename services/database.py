"""SQLite 資料庫連線管理與初始化"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 設定日誌
db_logger = logging.getLogger("core.database")

class Database:
    """資料庫管理類別"""

    def __init__(self, db_path: str = "chiayi_qa.db"):
        """初始化資料庫連線

        Args:
            db_path: SQLite 資料庫檔案路徑
        """
        self.db_path = db_path
        db_logger.info(f"初始化資料庫: {db_path}")
        self._init_database()

    @contextmanager
    def get_connection(self):
        """取得資料庫連線的 context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 讓結果可以用欄位名稱存取
        try:
            yield conn
            conn.commit()
            db_logger.debug("資料庫交易提交成功")
        except Exception as e:
            conn.rollback()
            db_logger.error(f"資料庫交易失敗，執行回滾: {e}")
            raise e
        finally:
            conn.close()

    def _init_database(self):
        """初始化資料庫結構"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 建立問題表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 建立答案表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 建立標籤表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 建立問題-答案關聯表（多對多）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS question_answers (
                    question_id INTEGER,
                    answer_id INTEGER,
                    priority INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (question_id, answer_id),
                    FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE,
                    FOREIGN KEY (answer_id) REFERENCES answers (id) ON DELETE CASCADE
                )
            ''')

            # 建立問題-標籤關聯表（多對多）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS question_tags (
                    question_id INTEGER,
                    tag_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (question_id, tag_id),
                    FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
                )
            ''')

            # 建立答案-標籤關聯表（多對多）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answer_tags (
                    answer_id INTEGER,
                    tag_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (answer_id, tag_id),
                    FOREIGN KEY (answer_id) REFERENCES answers (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
                )
            ''')

            # 建立索引以提升查詢效能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_questions_content ON questions(content)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_priority ON question_answers(priority DESC)')

            db_logger.info("資料庫結構初始化完成")

    def migrate_from_json(self, json_path: str = "docs/qa.json"):
        """從 JSON 檔案遷移資料到 SQLite

        Args:
            json_path: JSON 檔案路徑
        """
        json_file = Path(json_path)
        if not json_file.exists():
            db_logger.error(f"JSON 檔案不存在: {json_path}")
            raise FileNotFoundError(f"JSON 檔案不存在: {json_path}")

        db_logger.info(f"開始從 {json_path} 遷移資料")
        with open(json_file, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)

        db_logger.info(f"讀取到 {len(qa_data)} 筆問答資料")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            migrated_count = 0

            for item in qa_data:
                question_text = item.get('question', '')
                answer_text = item.get('answer', '')

                if not question_text or not answer_text:
                    db_logger.warning(f"跳過無效資料項: {item}")
                    continue

                # 插入或取得問題 ID
                cursor.execute('INSERT OR IGNORE INTO questions (content) VALUES (?)', (question_text,))
                cursor.execute('SELECT id FROM questions WHERE content = ?', (question_text,))
                question_id = cursor.fetchone()[0]

                # 插入或取得答案 ID
                cursor.execute('INSERT OR IGNORE INTO answers (content) VALUES (?)', (answer_text,))
                cursor.execute('SELECT id FROM answers WHERE content = ?', (answer_text,))
                answer_id = cursor.fetchone()[0]

                # 建立問題-答案關聯
                cursor.execute('''
                    INSERT OR IGNORE INTO question_answers (question_id, answer_id, priority)
                    VALUES (?, ?, ?)
                ''', (question_id, answer_id, 100))

                # 自動產生標籤（基於內容關鍵字）
                tags = self._extract_tags(question_text, answer_text)
                for tag_name in tags:
                    cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
                    cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                    tag_id = cursor.fetchone()[0]

                    # 關聯標籤到問題和答案
                    cursor.execute('INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)',
                                 (question_id, tag_id))
                    cursor.execute('INSERT OR IGNORE INTO answer_tags (answer_id, tag_id) VALUES (?, ?)',
                                 (answer_id, tag_id))

                migrated_count += 1
                db_logger.debug(f"成功遷移問答對: {question_text[:30]}...")

            db_logger.info(f"資料遷移完成，共遷移 {migrated_count} 筆問答對")

    def _extract_tags(self, question: str, answer: str) -> List[str]:
        """從問題和答案中提取標籤

        Args:
            question: 問題內容
            answer: 答案內容

        Returns:
            標籤列表
        """
        tags = []
        content = question + " " + answer

        # 關鍵字對應標籤
        keyword_tags = {
            ('阿里山', '森林鐵路', '小火車'): '阿里山',
            ('日出',): '日出',
            ('火雞肉飯', '砂鍋魚頭', '美食'): '美食',
            ('票', '買票', '訂票', '購票'): '購票',
            ('車站', '火車站'): '交通',
            ('第一次', '新手'): '新手指南',
            ('景點', '值得看'): '景點推薦',
            ('餐廳', '在地'): '在地美食'
        }

        for keywords, tag in keyword_tags.items():
            if any(keyword in content for keyword in keywords):
                tags.append(tag)

        # 如果沒有找到任何標籤，加入通用標籤
        if not tags:
            tags.append('一般')

        return tags


# 單例模式，確保整個應用只有一個資料庫實例
_db_instance: Optional[Database] = None

def get_database() -> Database:
    """取得資料庫實例（單例）"""
    global _db_instance
    if _db_instance is None:
        db_logger.info("建立資料庫單例實例")
        _db_instance = Database()
    return _db_instance