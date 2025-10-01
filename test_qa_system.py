#!/usr/bin/env python
"""測試 QA 系統功能"""

from services import get_qa_service, get_database


def test_qa_system():
    """測試 QA 系統各項功能"""
    print("=== 測試 QA 系統 ===\n")

    # 取得服務實例
    service = get_qa_service()
    db = get_database()

    # 1. 測試資料遷移
    print("1. 執行資料遷移...")
    try:
        db.migrate_from_json("docs/qa.json")
        print("✅ 遷移成功\n")
    except Exception as e:
        print(f"⚠️ 遷移可能已完成或發生錯誤: {e}\n")

    # 2. 測試問題查詢
    print("2. 測試問題查詢：")
    test_questions = [
        "第一次來嘉義",
        "阿里山怎麼去",
        "哪裡有好吃的",
        "如何買票",
        "謝謝"
    ]

    for q in test_questions:
        answer = service.find_answer(q)
        print(f"   Q: {q}")
        print(f"   A: {answer[:60]}..." if len(answer) > 60 else f"   A: {answer}")
        print()

    # 3. 測試標籤功能
    print("3. 標籤系統：")
    tags = service.get_all_tags()
    print(f"   總共 {len(tags)} 個標籤：")
    for tag_name, count in tags[:5]:  # 只顯示前5個
        print(f"   - {tag_name}: {count} 個相關內容")
    print()

    # 4. 測試根據標籤搜尋
    print("4. 根據標籤搜尋（標籤：美食）：")
    questions = service.get_questions_by_tag("美食")
    for q in questions[:3]:  # 只顯示前3個
        print(f"   - {q['content']}")
    if not questions:
        print("   無相關問題")
    print()

    # 5. 測試關鍵字搜尋
    print("5. 關鍵字搜尋（關鍵字：阿里山）：")
    results = service.search_questions("阿里山")
    for r in results[:3]:  # 只顯示前3個
        tags = ', '.join(r['tags']) if r['tags'] else '無標籤'
        print(f"   - {r['content']} [標籤: {tags}]")
    if not results:
        print("   無搜尋結果")
    print()

    # 6. 測試新增問答對
    print("6. 測試新增問答對：")
    success = service.add_qa_pair(
        question="嘉義有什麼特色伴手禮？",
        answer="嘉義的特色伴手禮有方塊酥、老楊方塊酥、噴水雞肉飯調理包等。",
        tags=["美食", "伴手禮", "購物"],
        priority=80
    )
    if success:
        print("✅ 新增成功")
        # 驗證新增的內容
        answer = service.find_answer("伴手禮")
        print(f"   驗證查詢: {answer[:60]}...")
    else:
        print("❌ 新增失敗")

    print("\n=== 測試完成 ===")


if __name__ == "__main__":
    test_qa_system()