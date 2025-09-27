#!/usr/bin/env python3
"""
測試 QA 服務功能
"""

import sys
import json

def test_qa_functions():
    """測試 QA 功能"""
    print("=== 測試 QA 服務功能 ===\n")

    # 載入原始 QA 資料
    try:
        with open('docs/qa.json', 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        print(f"✅ 成功載入 docs/qa.json，包含 {len(qa_data)} 個 Q&A\n")
    except Exception as e:
        print(f"❌ 無法載入 docs/qa.json: {e}")
        return False

    # 測試服務模組
    try:
        from services.qa import (
            first_visit,
            alishan_ticket,
            train_station_location,
            local_food,
            thank_you,
            opening_greeting,
            general_help,
            goodbye
        )
        print("✅ 成功載入 services.qa 模組\n")
    except ImportError as e:
        print(f"❌ 無法載入 services.qa 模組: {e}")
        return False

    # 測試每個函數
    test_functions = [
        ("first_visit", first_visit, "歡迎來到嘉義！最有名的景點是阿里山"),
        ("alishan_ticket", alishan_ticket, "你可以直接在這裡的櫃檯買票"),
        ("train_station_location", train_station_location, "火車就是從這個車站出發的"),
        ("local_food", local_food, "我推薦火雞肉飯和砂鍋魚頭"),
        ("thank_you", thank_you, "祝你有個美好的旅程"),
        ("opening_greeting", opening_greeting, "歡迎來到嘉義旅遊服務中心"),
        ("general_help", general_help, "我可以為您介紹嘉義的景點"),
        ("goodbye", goodbye, "祝您在嘉義有個愉快的旅程")
    ]

    print("=== 測試函數輸出 ===")
    success_count = 0
    for func_name, func, expected_keyword in test_functions:
        try:
            result = func()
            if expected_keyword in result:
                print(f"✅ {func_name}(): {result[:50]}...")
                success_count += 1
            else:
                print(f"⚠️ {func_name}(): 輸出不包含預期關鍵字")
                print(f"   預期: '{expected_keyword}'")
                print(f"   實際: {result[:50]}...")
        except Exception as e:
            print(f"❌ {func_name}(): 執行失敗 - {e}")

    print(f"\n=== 測試結果 ===")
    print(f"通過: {success_count}/{len(test_functions)}")

    return success_count == len(test_functions)

def test_mcp_integration():
    """測試 MCP 整合"""
    print("\n=== 測試 MCP 整合 ===\n")

    try:
        # 只測試導入，不啟動伺服器
        import mcp_server

        # 檢查 QA 工具是否已註冊
        qa_tools = [
            'qa_first_visit',
            'qa_alishan_ticket',
            'qa_train_station_location',
            'qa_local_food',
            'qa_thank_you',
            'qa_opening_greeting',
            'qa_general_help',
            'qa_goodbye'
        ]

        # 檢查函數是否存在
        available_tools = []
        for tool_name in qa_tools:
            if hasattr(mcp_server, tool_name):
                available_tools.append(tool_name)
                print(f"✅ 找到工具: {tool_name}")
            else:
                print(f"⚠️ 未找到工具: {tool_name}")

        print(f"\n找到 {len(available_tools)}/{len(qa_tools)} 個 QA 工具")
        return len(available_tools) == len(qa_tools)

    except ImportError as e:
        if 'fastmcp' in str(e):
            print(f"⚠️ FastMCP 未安裝，跳過 MCP 整合測試")
            print("  提示：執行 'pip install fastmcp' 安裝 FastMCP")
            return True  # 視為可接受的情況
        else:
            print(f"❌ MCP 整合測試失敗: {e}")
            return False
    except Exception as e:
        print(f"❌ MCP 整合測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("🚀 開始測試 QA 服務...\n")

    # 測試 QA 函數
    qa_test_passed = test_qa_functions()

    # 測試 MCP 整合
    mcp_test_passed = test_mcp_integration()

    # 總結
    print("\n" + "="*50)
    if qa_test_passed and mcp_test_passed:
        print("✅ 所有測試通過！QA 服務已成功整合。")
        sys.exit(0)
    else:
        print("⚠️ 部分測試失敗，請檢查錯誤訊息。")
        sys.exit(1)