"""QA 問答服務模組 - 使用 SQLite 資料庫管理"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from .database import get_database
import sqlite3

# 設定日誌
qa_logger = logging.getLogger("core.qa")


class QAService:
    """QA 服務類別，提供問答系統的 CRUD 操作"""

    def __init__(self):
        """初始化 QA 服務"""
        self.db = get_database()

    def find_answer(self, question: str) -> str:
        """根據問題尋找最佳答案

        Args:
            question: 用戶的問題

        Returns:
            最相關的答案，如果找不到則返回預設回應
        """
        qa_logger.info(f"查詢問題: {question}")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 嘗試精確匹配
            cursor.execute('''
                SELECT a.content, qa.priority
                FROM questions q
                JOIN question_answers qa ON q.id = qa.question_id
                JOIN answers a ON qa.answer_id = a.id
                WHERE LOWER(q.content) = LOWER(?)
                ORDER BY qa.priority DESC
                LIMIT 1
            ''', (question,))
            result = cursor.fetchone()
            if result:
                qa_logger.info(f"找到精確匹配答案: {result[0][:50]}...")
                return result[0]

            # 2. 嘗試部分匹配
            cursor.execute('''
                SELECT a.content, qa.priority,
                       CASE
                           WHEN LOWER(q.content) LIKE '%' || LOWER(?) || '%' THEN 2
                           WHEN LOWER(?) LIKE '%' || LOWER(q.content) || '%' THEN 1
                           ELSE 0
                       END as match_score
                FROM questions q
                JOIN question_answers qa ON q.id = qa.question_id
                JOIN answers a ON qa.answer_id = a.id
                WHERE LOWER(q.content) LIKE '%' || LOWER(?) || '%'
                   OR LOWER(?) LIKE '%' || LOWER(q.content) || '%'
                ORDER BY match_score DESC, qa.priority DESC
                LIMIT 1
            ''', (question, question, question, question))
            result = cursor.fetchone()
            if result:
                qa_logger.info(f"找到部分匹配答案 (匹配分數: {result[1]}): {result[0][:50]}...")
                return result[0]

            # 3. 嘗試標籤匹配
            keywords = self._extract_keywords(question)
            if keywords:
                placeholders = ','.join('?' * len(keywords))
                cursor.execute(f'''
                    SELECT a.content, COUNT(DISTINCT t.id) as tag_count
                    FROM tags t
                    JOIN answer_tags at ON t.id = at.tag_id
                    JOIN answers a ON at.answer_id = a.id
                    WHERE LOWER(t.name) IN ({placeholders})
                    GROUP BY a.id, a.content
                    ORDER BY tag_count DESC
                    LIMIT 1
                ''', keywords)
                result = cursor.fetchone()
                if result:
                    qa_logger.info(f"找到標籤匹配答案 (標籤數: {result[1]}): {result[0][:50]}...")
                    return result[0]

            qa_logger.warning(f"找不到答案: {question}")
            return "不好意思，我沒有理解您的問題。請問您想了解嘉義的哪方面資訊噢？"

    def add_qa_pair(self, question: str, answer: str, tags: List[str] = None, priority: int = 50) -> bool:
        """新增問答對

        Args:
            question: 問題內容
            answer: 答案內容
            tags: 標籤列表
            priority: 優先級（0-100）

        Returns:
            是否新增成功
        """
        qa_logger.info(f"新增問答對 - Q: {question[:30]}..., Tags: {tags}")
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 插入問題
                cursor.execute('INSERT OR IGNORE INTO questions (content) VALUES (?)', (question,))
                cursor.execute('SELECT id FROM questions WHERE content = ?', (question,))
                question_id = cursor.fetchone()[0]

                # 插入答案
                cursor.execute('INSERT OR IGNORE INTO answers (content) VALUES (?)', (answer,))
                cursor.execute('SELECT id FROM answers WHERE content = ?', (answer,))
                answer_id = cursor.fetchone()[0]

                # 建立關聯
                cursor.execute('''
                    INSERT OR REPLACE INTO question_answers (question_id, answer_id, priority)
                    VALUES (?, ?, ?)
                ''', (question_id, answer_id, priority))

                # 處理標籤
                if tags:
                    for tag_name in tags:
                        cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
                        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                        tag_id = cursor.fetchone()[0]

                        cursor.execute('INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)',
                                     (question_id, tag_id))
                        cursor.execute('INSERT OR IGNORE INTO answer_tags (answer_id, tag_id) VALUES (?, ?)',
                                     (answer_id, tag_id))

                qa_logger.info(f"成功新增問答對: {question[:30]}...")
                return True
        except Exception as e:
            qa_logger.error(f"新增問答對失敗: {e}")
            return False

    def get_questions_by_tag(self, tag_name: str) -> List[Dict[str, Any]]:
        """根據標籤獲取相關問題

        Args:
            tag_name: 標籤名稱

        Returns:
            相關問題列表
        """
        qa_logger.debug(f"搜尋標籤: {tag_name}")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT q.id, q.content
                FROM questions q
                JOIN question_tags qt ON q.id = qt.question_id
                JOIN tags t ON qt.tag_id = t.id
                WHERE LOWER(t.name) = LOWER(?)
            ''', (tag_name,))

            results = [{'id': row[0], 'content': row[1]} for row in cursor.fetchall()]
            qa_logger.info(f"找到 {len(results)} 個標籤 '{tag_name}' 相關問題")
            return results

    def get_all_tags(self) -> List[Tuple[str, int]]:
        """獲取所有標籤及其使用次數

        Returns:
            標籤列表，格式為 [(標籤名, 使用次數)]
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.name,
                       COUNT(DISTINCT qt.question_id) + COUNT(DISTINCT at.answer_id) as usage_count
                FROM tags t
                LEFT JOIN question_tags qt ON t.id = qt.tag_id
                LEFT JOIN answer_tags at ON t.id = at.tag_id
                GROUP BY t.id, t.name
                ORDER BY usage_count DESC
            ''')

            return cursor.fetchall()

    def search_questions(self, keyword: str) -> List[Dict[str, Any]]:
        """搜尋包含關鍵字的問題

        Args:
            keyword: 搜尋關鍵字

        Returns:
            相關問題列表
        """
        qa_logger.debug(f"搜尋關鍵字: {keyword}")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.id, q.content, GROUP_CONCAT(t.name, ', ') as tags
                FROM questions q
                LEFT JOIN question_tags qt ON q.id = qt.question_id
                LEFT JOIN tags t ON qt.tag_id = t.id
                WHERE LOWER(q.content) LIKE '%' || LOWER(?) || '%'
                GROUP BY q.id, q.content
                ORDER BY q.created_at DESC
            ''', (keyword,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'content': row[1],
                    'tags': row[2].split(', ') if row[2] else []
                })
            qa_logger.info(f"找到 {len(results)} 個包含 '{keyword}' 的問題")
            return results

    def _extract_keywords(self, text: str) -> List[str]:
        """從文字中提取關鍵字

        Args:
            text: 輸入文字

        Returns:
            關鍵字列表
        """
        keywords = []
        keyword_map = {
            '阿里山': ['阿里山', '森林鐵路', '小火車'],
            '日出': ['日出', '日落'],
            '美食': ['美食', '火雞肉飯', '砂鍋魚頭', '餐廳'],
            '購票': ['票', '買票', '訂票', '購票'],
            '交通': ['車站', '火車', '交通'],
            '景點': ['景點', '觀光', '旅遊']
        }

        text_lower = text.lower()
        for tag, words in keyword_map.items():
            if any(word in text_lower for word in words):
                keywords.append(tag.lower())

        return keywords


# 保持向後相容的函數介面
_qa_service = None

def get_qa_service() -> QAService:
    """取得 QA 服務實例（單例）"""
    global _qa_service
    if _qa_service is None:
        qa_logger.info("建立 QA 服務單例實例")
        _qa_service = QAService()
    return _qa_service


def find_answer(question: str, qa_file_path: str = None) -> str:
    """向後相容的函數介面

    Args:
        question: 用戶的問題
        qa_file_path: 保留參數，為了向後相容（不再使用）

    Returns:
        對應的答案
    """
    service = get_qa_service()
    return service.find_answer(question)


def get_all_questions(qa_file_path: str = None) -> List[str]:
    """向後相容的函數介面

    Args:
        qa_file_path: 保留參數，為了向後相容（不再使用）

    Returns:
        所有問題的列表
    """
    service = get_qa_service()
    with service.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content FROM questions ORDER BY created_at DESC')
        return [row[0] for row in cursor.fetchall()]


# 保留原有的簡單函數介面（向後相容）
# def first_visit():
#     """問題: 這是我第一次來嘉義，可以告訴我有什麼特別值得看的嗎？"""
#     return find_answer("這是我第一次來嘉義，可以告訴我有什麼特別值得看的嗎？")


# def alishan_ticket():
#     """問題: 阿里山森林鐵路聽起來好棒！我要怎麼買票呢？"""
#     return find_answer("阿里山森林鐵路聽起來好棒！我要怎麼買票呢？")


# def train_station_location():
#     """問題: 搭去阿里山的火車站就在附近嗎？"""
#     return find_answer("搭去阿里山的火車站就在附近嗎？")


# def local_food():
#     """問題: 我在哪裡可以嘗到在地的美食呢？"""
#     return find_answer("我在哪裡可以嘗到在地的美食呢？")


# def thank_you():
#     """問題: 謝謝你！"""
#     return find_answer("謝謝你！")