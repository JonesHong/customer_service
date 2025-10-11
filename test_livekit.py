#!/usr/bin/env python
"""測試 LiveKit 連接"""
import asyncio
import os
import logging
from dotenv import load_dotenv
from livekit import api

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """測試 LiveKit 連接"""

    # 取得環境變數
    url = os.getenv('LIVEKIT_URL')
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')

    logger.info(f"LiveKit URL: {url}")
    logger.info(f"API Key: {api_key[:10]}..." if api_key else "API Key not found")
    logger.info(f"API Secret: {api_secret[:10]}..." if api_secret else "API Secret not found")

    if not all([url, api_key, api_secret]):
        logger.error("Missing required environment variables!")
        return

    # 測試生成 token
    try:
        token = api.AccessToken(api_key=api_key, api_secret=api_secret)
        token.with_identity("test-agent")
        token.with_grants(api.VideoGrants(room_join=True, room="test-room"))

        jwt_token = token.to_jwt()
        logger.info(f"Token generated successfully: {jwt_token[:50]}...")

        # 嘗試連接
        from livekit import rtc

        room = rtc.Room()

        @room.on("connected")
        def on_connected():
            logger.info("✅ Successfully connected to LiveKit!")

        @room.on("connection_state_changed")
        def on_state_changed(state):
            logger.info(f"Connection state: {state}")

        logger.info("Attempting to connect to LiveKit...")
        await room.connect(url, jwt_token)

        # 等待一秒
        await asyncio.sleep(1)

        # 斷開連接
        await room.disconnect()
        logger.info("Test completed successfully!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())