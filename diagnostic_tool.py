"""
診斷工具：追蹤 LiveKit 訊息流

這個工具可以幫助診斷文字訊息從前端到後端的完整流程。

使用方法：
1. 在另一個終端運行這個診斷工具：python diagnostic_tool.py
2. 在主終端運行 agent：python agent.py dev
3. 從前端發送測試訊息
4. 對比兩邊的日誌輸出
"""

import asyncio
import logging
from livekit import rtc, api
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class MessageFlowDiagnostic:
    """訊息流診斷工具"""

    def __init__(self):
        self.room = None
        self.message_count = 0

    async def setup_diagnostic_room(self, room_name: str):
        """設置診斷用的房間連接"""
        logger.info("=" * 80)
        logger.info("🔧 [DIAGNOSTIC] Setting up diagnostic room connection")
        logger.info(f"🔧 [DIAGNOSTIC] Target room: {room_name}")

        # 創建訪問令牌
        livekit_url = os.getenv("LIVEKIT_URL")
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")

        logger.info(f"🔧 [DIAGNOSTIC] LiveKit URL: {livekit_url}")
        logger.info(f"🔧 [DIAGNOSTIC] API Key: {api_key[:10]}...")

        # 使用 LiveKit API 創建令牌
        token_api = api.AccessToken(api_key, api_secret)
        token_api.with_identity("diagnostic-observer")
        token_api.with_name("Diagnostic Observer")
        token_api.with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_subscribe=True,
            can_publish=False,
            can_publish_data=False
        ))

        token = token_api.to_jwt()
        logger.info("✅ [DIAGNOSTIC] Access token created")

        # 連接到房間
        self.room = rtc.Room()

        # 註冊所有可能的事件監聽器
        self.register_all_event_listeners()

        logger.info("🔧 [DIAGNOSTIC] Connecting to room...")
        await self.room.connect(livekit_url, token)
        logger.info("✅ [DIAGNOSTIC] Connected to room successfully")
        logger.info(f"✅ [DIAGNOSTIC] Room SID: {self.room.sid}")
        logger.info(f"✅ [DIAGNOSTIC] Local participant: {self.room.local_participant.identity}")
        logger.info("=" * 80)

    def register_all_event_listeners(self):
        """註冊所有可能的事件監聽器來追蹤訊息流"""

        logger.info("🔧 [DIAGNOSTIC] Registering event listeners...")

        # 1. Data received event (最關鍵的事件)
        @self.room.on("data_received")
        def on_data_received(data_packet: rtc.DataPacket):
            self.message_count += 1
            logger.info("=" * 80)
            logger.info(f"🎯 [DATA_RECEIVED #{self.message_count}] DATA PACKET RECEIVED!")
            logger.info(f"📊 [DATA_RECEIVED] Packet type: {type(data_packet)}")
            logger.info(f"📊 [DATA_RECEIVED] Kind: {data_packet.kind}")
            logger.info(f"📊 [DATA_RECEIVED] Topic: {data_packet.topic}")

            if data_packet.participant:
                logger.info(f"📊 [DATA_RECEIVED] Participant: {data_packet.participant.identity}")
                logger.info(f"📊 [DATA_RECEIVED] Participant SID: {data_packet.participant.sid}")
            else:
                logger.info("📊 [DATA_RECEIVED] Participant: None")

            try:
                # 解碼二進制數據
                raw_data = data_packet.data
                logger.info(f"📥 [DATA_RECEIVED] Raw data type: {type(raw_data)}")
                logger.info(f"📥 [DATA_RECEIVED] Raw data length: {len(raw_data)} bytes")

                # 嘗試解碼為 UTF-8 文本
                text = raw_data.decode('utf-8')
                logger.info(f"📥 [DATA_RECEIVED] Decoded text: {text}")

                # 嘗試解析 JSON
                import json
                try:
                    payload = json.loads(text)
                    logger.info(f"📥 [DATA_RECEIVED] Parsed JSON payload:")
                    for key, value in payload.items():
                        logger.info(f"   - {key}: {value}")
                except json.JSONDecodeError:
                    logger.info(f"📥 [DATA_RECEIVED] Not JSON, raw text: {text}")

            except UnicodeDecodeError as e:
                logger.error(f"❌ [DATA_RECEIVED] Failed to decode as UTF-8: {e}")
                logger.error(f"❌ [DATA_RECEIVED] Raw bytes: {raw_data[:100]}")
            except Exception as e:
                logger.error(f"❌ [DATA_RECEIVED] Error processing data: {e}")
                import traceback
                logger.error(traceback.format_exc())

            logger.info("=" * 80)

        # 2. Participant connected
        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info("=" * 80)
            logger.info(f"👤 [PARTICIPANT] New participant connected: {participant.identity}")
            logger.info(f"👤 [PARTICIPANT] Participant SID: {participant.sid}")
            logger.info("=" * 80)

        # 3. Participant disconnected
        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info("=" * 80)
            logger.info(f"👤 [PARTICIPANT] Participant disconnected: {participant.identity}")
            logger.info("=" * 80)

        # 4. Room metadata updated
        @self.room.on("room_metadata_changed")
        def on_room_metadata_changed(metadata: str):
            logger.info("=" * 80)
            logger.info(f"📝 [METADATA] Room metadata changed: {metadata}")
            logger.info("=" * 80)

        # 5. Connection state changed
        @self.room.on("connection_state_changed")
        def on_connection_state_changed(state: rtc.ConnectionState):
            logger.info("=" * 80)
            logger.info(f"🔌 [CONNECTION] Connection state changed: {state}")
            logger.info("=" * 80)

        # 6. Track published
        @self.room.on("track_published")
        def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info("=" * 80)
            logger.info(f"🎵 [TRACK] Track published by {participant.identity}")
            logger.info(f"🎵 [TRACK] Track SID: {publication.sid}")
            logger.info(f"🎵 [TRACK] Track kind: {publication.kind}")
            logger.info("=" * 80)

        logger.info("✅ [DIAGNOSTIC] All event listeners registered")

    async def monitor_messages(self, duration_seconds: int = 300):
        """監控訊息一段時間"""
        logger.info("=" * 80)
        logger.info(f"👀 [DIAGNOSTIC] Starting message monitoring for {duration_seconds} seconds")
        logger.info("👀 [DIAGNOSTIC] Send messages from frontend to see them here")
        logger.info("=" * 80)

        try:
            await asyncio.sleep(duration_seconds)
        except KeyboardInterrupt:
            logger.info("\n⏹️  [DIAGNOSTIC] Monitoring stopped by user")

        logger.info("=" * 80)
        logger.info(f"📊 [DIAGNOSTIC] Monitoring completed")
        logger.info(f"📊 [DIAGNOSTIC] Total messages received: {self.message_count}")
        logger.info("=" * 80)

async def main():
    """主函數"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          LiveKit 訊息流診斷工具                              ║
╚══════════════════════════════════════════════════════════════╝

這個工具會以觀察者身份連接到 LiveKit 房間，
監聽所有 data_received 事件，幫助診斷訊息流問題。

使用步驟：
1. 確保 .env 文件已配置 LiveKit 憑證
2. 運行這個診斷工具
3. 在另一個終端運行 agent: python agent.py dev
4. 從前端發送測試訊息
5. 觀察這個工具的輸出

按 Ctrl+C 停止監控
""")

    # 詢問房間名稱（或使用默認值）
    room_name = input("請輸入房間名稱（直接按 Enter 使用默認值 'test-room'）: ").strip()
    if not room_name:
        room_name = "test-room"

    diagnostic = MessageFlowDiagnostic()

    try:
        await diagnostic.setup_diagnostic_room(room_name)
        await diagnostic.monitor_messages()
    except Exception as e:
        logger.error(f"❌ [ERROR] Diagnostic tool failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if diagnostic.room:
            await diagnostic.room.disconnect()
            logger.info("✅ [DIAGNOSTIC] Disconnected from room")

if __name__ == "__main__":
    asyncio.run(main())
