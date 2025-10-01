#!/usr/bin/env python
"""資料遷移腳本 - 從 JSON 遷移到 SQLite"""

import sys
from pathlib import Path
from services.database import get_database
from services.qa import get_qa_service


def migrate_data():
    """執行資料遷移"""
    print("開始資料遷移...")

    # 初始化資料庫
    db = get_database()

    # 執行遷移
    try:
        db.migrate_from_json("docs/qa.json")
        print("✅ 資料遷移成功！")

        # 驗證遷移結果
        service = get_qa_service()

        # 顯示統計資訊
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM questions')
            question_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM answers')
            answer_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM tags')
            tag_count = cursor.fetchone()[0]

            print(f"\n統計資訊：")
            print(f"  問題數量：{question_count}")
            print(f"  答案數量：{answer_count}")
            print(f"  標籤數量：{tag_count}")

            # 顯示所有標籤
            tags = service.get_all_tags()
            print(f"\n標籤列表：")
            for tag_name, usage_count in tags:
                print(f"  - {tag_name}: {usage_count} 次使用")

            # 測試查詢
            print("\n測試查詢：")
            test_questions = [
                "第一次來嘉義",
                "阿里山",
                "美食"
            ]

            for q in test_questions:
                answer = service.find_answer(q)
                print(f"  Q: {q}")
                print(f"  A: {answer[:50]}..." if len(answer) > 50 else f"  A: {answer}")
                print()

    except FileNotFoundError as e:
        print(f"❌ 錯誤：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 遷移失敗：{e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate_data()