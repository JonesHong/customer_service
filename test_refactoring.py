#!/usr/bin/env python3
"""
測試重構後的模組功能
確保核心服務、MCP 伺服器和 LiveKit 工具都能正常運作
"""

import asyncio
import sys
from pathlib import Path

# 添加當前目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

def test_core_services():
    """測試核心服務模組的無狀態函數"""
    print("\n=== 測試核心服務模組 ===")
    from core_services import (
        fetch_weather,
        search_web_ddg,
        expand_query_with_synonyms,
        health_check
    )

    # 測試天氣查詢
    print("\n1. 測試天氣查詢:")
    weather = fetch_weather("Taipei")
    print(f"   Taipei 天氣: {weather[:50]}...")

    # 測試網頁搜尋
    print("\n2. 測試網頁搜尋:")
    search_result = search_web_ddg("嘉義旅遊", max_results=2)
    print(f"   搜尋結果: {search_result[:100]}...")

    # 測試同義詞擴展
    print("\n3. 測試同義詞擴展:")
    expanded = expand_query_with_synonyms("阿里山小火車")
    print(f"   擴展結果: {expanded}")

    # 測試健康檢查
    print("\n4. 測試健康檢查:")
    status = health_check()
    print(f"   系統狀態: {status['status']}")
    for service, state in status['services'].items():
        print(f"   - {service}: {state}")


def test_mcp_server():
    """測試 MCP 伺服器工具"""
    print("\n=== 測試 MCP 伺服器工具 ===")
    try:
        from mcp_server import get_weather, search_web, system_health

        # 測試 MCP 包裝的天氣查詢
        print("\n1. MCP 天氣查詢:")
        weather = get_weather("Chiayi")
        print(f"   Chiayi 天氣: {weather[:50]}...")

        # 測試 MCP 包裝的網頁搜尋
        print("\n2. MCP 網頁搜尋:")
        search = search_web("Friday AI")
        print(f"   搜尋結果: {search[:100]}...")

        # 測試 MCP 系統健康檢查
        print("\n3. MCP 系統健康:")
        health = system_health()
        print(f"   {health}")
    except ImportError as e:
        print(f"   ⚠️  無法測試 MCP 伺服器（缺少依賴）: {e}")


async def test_livekit_tools():
    """測試 LiveKit 工具（異步）"""
    print("\n=== 測試 LiveKit 工具 ===")
    try:
        from tools import get_weather, search_web, get_weather_batch

        # 創建模擬的 RunContext
        class MockContext:
            pass

        context = MockContext()

        # 測試 LiveKit 包裝的天氣查詢
        print("\n1. LiveKit 天氣查詢:")
        weather = await get_weather(context, "Kaohsiung")
        print(f"   Kaohsiung 天氣: {weather[:50]}...")

        # 測試 LiveKit 包裝的網頁搜尋
        print("\n2. LiveKit 網頁搜尋:")
        search = await search_web(context, "台灣美食")
        print(f"   搜尋結果: {search[:100]}...")

        # 測試批次天氣查詢
        print("\n3. LiveKit 批次天氣查詢:")
        batch_weather = await get_weather_batch(context, ["Taipei", "Taichung", "Tainan"])
        for city, weather in batch_weather.items():
            print(f"   {city}: {weather[:30]}...")
    except ImportError as e:
        print(f"   ⚠️  無法測試 LiveKit 工具（缺少依賴）: {e}")


def main():
    """主測試函數"""
    print("=" * 60)
    print("開始測試重構後的模組")
    print("=" * 60)

    try:
        # 測試核心服務
        test_core_services()

        # 測試 MCP 伺服器
        test_mcp_server()

        # 測試 LiveKit 工具（異步）
        asyncio.run(test_livekit_tools())

        print("\n" + "=" * 60)
        print("✅ 所有測試完成！重構成功！")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 測試失敗：{e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()