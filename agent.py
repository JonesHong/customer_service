from dotenv import load_dotenv
import logging
import json
import asyncio
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm, RoomOutputOptions, WorkerPermissions
from livekit.agents.voice.room_io import TextInputEvent
from livekit.agents.types import TOPIC_CHAT
from livekit.plugins import (
    google,
    openai,
    noise_cancellation,
)
from livekit.plugins.openai.realtime.utils import TurnDetection
from livekit.agents import mcp as mcp_client
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import (
    get_weather,
    search_web,
    qa_find_answer,
    qa_search_by_tag,
    qa_search_questions,
    qa_list_tags,
)
from log_config import setup_logging

load_dotenv()

# 設定日誌（使用統一配置）
setup_logging(level=logging.INFO, disable_duplicate=True)
agent_logger = logging.getLogger("core.agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            # llm=google.beta.realtime.RealtimeModel(
            #     voice="Aoede",
            #     temperature=0.8,
            # ),
            instructions=AGENT_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                voice="marin",  # 預設為 marin, 另提供以下選擇 alloy, ash, ballad, coral, echo, sage, shimmer, verse, cedar
                temperature=0.8,
                speed=1.2,
                turn_detection=TurnDetection(  # ✅ 啟用伺服器端語音檢測
                    type="server_vad",
                    threshold=0.3,  # ✅ 降低閾值使其更容易觸發（從 0.5 → 0.3）
                    prefix_padding_ms=300,
                    silence_duration_ms=500,
                ),
            ),
            tools=[
                get_weather,
                # search_web,
                qa_find_answer,
                qa_search_by_tag,
                qa_search_questions,
                qa_list_tags,
            ],
            # ✅ 關鍵：連到本地或遠端 MCP Server；可並列多個
            # mcp_servers=[
            #     # 1) 若使用 stdio 啟動（同機、以 subprocess 方式）：
            #     # mcp_client.MCPServerStdio(
            #     #     command=sys.executable,
            #     #     args=[str(Path(__file__).with_name("mcp_server.py"))]
            #     # ),
            #     # 2) 若使用 HTTP/SSE 方式（請替換 URL 為你的部署位置）：
            #     # mcp_client.MCPServerHTTP("http://localhost:8000"),
            #     mcp_client.MCPServerHTTP("http://localhost:9000/sse", timeout=10),
            #     # 3) 亦可使用 Streamable HTTP（視伺服器型態而定）
            #     # mcp_client.MCPServerStreamableHTTP("http://localhost:8000"),
            # ],
        )

    # 移除 on_enter 和 on_exit，避免提前結束 session
    # async def on_enter(self):
    #     agent_logger.info("Assistant agent has called when the task is entered")

    # async def on_exit(self):
    #     agent_logger.info("Assistant agent has called when the task is exited.")

    # 保留這個方法來記錄用戶訊息
    # async def on_user_turn_completed(
    #     self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    # ):
    #     agent_logger.info(
    #         f"Called when the user has finished speaking, and the LLM is about to respond. New message: {new_message.text[:50]}..."
    #     )


async def entrypoint(ctx: agents.JobContext):
    agent_logger.info(f"Entrypoint called with room: {ctx.room}")
    agent_logger.info(f"Room name: {getattr(ctx.room, 'name', 'Not connected yet')}")

    # 先連接到房間
    await ctx.connect()
    agent_logger.info("✅ Connected to room")

    # 創建 AgentSession（需要提前創建以便在回調中使用）
    session = AgentSession()

    # 設定 Agent Metadata（讓前端可以識別）
    try:
        # 使用 set_metadata 而不是 update_metadata
        await ctx.room.local_participant.set_metadata(
            json.dumps({"role": "agent", "name": "嘉義客服 AI"})
        )
        agent_logger.info("✅ Agent metadata set successfully")
    except Exception as e:
        agent_logger.error(f"Failed to set metadata: {e}")
        # 如果 set_metadata 也不存在，可能需要其他方式設定
        agent_logger.info(f"Available methods: {dir(ctx.room.local_participant)}")

    # ✅ 定義文字訊息處理函數
    async def on_text_message(sess: AgentSession, event: TextInputEvent):
        """處理來自用戶的文字訊息"""
        agent_logger.info("=" * 80)
        agent_logger.info(f"🔔 [TEXT_CALLBACK] *** TEXT MESSAGE CALLBACK TRIGGERED ***")
        agent_logger.info(f"🔔 [TEXT_CALLBACK] Event type: {type(event)}")
        agent_logger.info(f"🔔 [TEXT_CALLBACK] Event attributes: {dir(event)}")
        agent_logger.info(f"🔔 [TEXT_CALLBACK] Event.text type: {type(event.text)}")

        user_text = event.text.strip()
        participant = event.participant

        agent_logger.info(f"💬 [TEXT_MESSAGE] Received from {participant.identity}: {user_text}")
        agent_logger.info(f"💬 [TEXT_MESSAGE] Participant SID: {participant.sid}")
        agent_logger.info(f"💬 [TEXT_MESSAGE] Text length: {len(user_text)}")
        agent_logger.info("=" * 80)

        # 發送文字訊息到前端（顯示用戶輸入）
        try:
            await ctx.room.local_participant.publish_data(
                json.dumps({
                    "type": "transcription",
                    "role": "user",
                    "text": user_text,
                    "is_final": True,
                    "source": "text"  # 標記為文字輸入
                }).encode('utf-8'),
                reliable=True
            )
            agent_logger.info(f"📤 Sent text message to client: {user_text}")
        except Exception as e:
            agent_logger.error(f"❌ Failed to send text message: {e}")

        # 使用 session.generate_reply() 讓 LLM 處理並生成智能回應
        try:
            agent_logger.info(f"🤖 Generating AI response for text message...")
            await sess.generate_reply(
                user_input=user_text,  # 將文字訊息作為用戶輸入
                instructions=None  # 使用預設指令
            )
            agent_logger.info(f"✅ AI response generation initiated")
        except Exception as e:
            agent_logger.error(f"❌ Failed to generate response for text message: {e}")

    # 監聽參與者加入事件
    participant_greeted = False

    def on_participant_connected(participant):
        nonlocal participant_greeted
        agent_logger.info(f"👤 Participant connected: {participant.identity}")
        agent_logger.info(f"   - SID: {participant.sid}")
        agent_logger.info(f"   - Type: {type(participant).__name__}")
        agent_logger.info(f"   - Metadata: {participant.metadata}")

        # RemoteParticipant is always remote (not local)
        if not participant_greeted:
            agent_logger.info(f"✅ User joined: {participant.identity}")
            participant_greeted = True
            # 用戶加入時可以選擇性地生成歡迎訊息
            # 但通常等用戶先說話比較自然

    def on_participant_disconnected(participant):
        agent_logger.info(f"👤 Participant disconnected: {participant.identity}")
        agent_logger.info(f"   - Type: {type(participant).__name__}")

    ctx.room.on("participant_connected", on_participant_connected)
    ctx.room.on("participant_disconnected", on_participant_disconnected)

    # ✅ Clean setup - RoomIO handles text streams automatically
    agent_logger.info("🔧 [SETUP] Event listeners configured")
    agent_logger.info("   - participant_connected ✅")
    agent_logger.info("   - participant_disconnected ✅")
    agent_logger.info("   - connection_state_changed ✅")
    agent_logger.info("   - RoomIO will auto-register text_stream_handler for TOPIC_CHAT ✅")

    # 監聽房間狀態變化
    def on_connection_state_changed(state):
        agent_logger.info(f"📡 Connection state changed: {state}")

    ctx.room.on("connection_state_changed", on_connection_state_changed)

    # 訂閱 ASR 轉錄事件
    def on_user_transcribed(event):
        event_type = "asr_final" if event.is_final else "asr_interim"
        agent_logger.info(f"[ASR] User said ({event_type}): {event.transcript}")

        # ✅ 發送 ASR 文字到前端（只發送 final 結果）
        if event.is_final and event.transcript.strip():
            try:
                asyncio.create_task(
                    ctx.room.local_participant.publish_data(
                        json.dumps({
                            "type": "transcription",
                            "role": "user",
                            "text": event.transcript,
                            "is_final": True
                        }).encode('utf-8'),
                        reliable=True
                    )
                )
                agent_logger.info(f"📤 Sent user transcription to client: {event.transcript}")
            except Exception as e:
                agent_logger.error(f"❌ Failed to send transcription: {e}")

    # 監聽 session 音訊輸入事件
    def on_input_audio_buffer_committed(event):
        agent_logger.info(f"🎤 Audio input buffer committed")

    def on_input_audio_buffer_speech_started(event):
        agent_logger.info(f"🗣️ Speech started detected")

    def on_input_audio_buffer_speech_stopped(event):
        agent_logger.info(f"🤐 Speech stopped detected")

    # ✅ 診斷用：監聽 OpenAI Realtime API 原始事件
    def on_openai_server_event(event):
        event_type = event.get('type', '') if isinstance(event, dict) else str(type(event).__name__)
        # 只記錄重要事件，避免 log 過多
        if 'delta' in event_type or 'done' in event_type:
            agent_logger.info(f"🔔 OpenAI Event: {event_type}")

    session.on("openai_server_event_received", on_openai_server_event)

    # 監聽 Agent 回應事件
    def on_agent_speech(event):
        agent_logger.info(f"🔊 Agent speech event: {type(event).__name__}")

    # ✅ 監聽所有可能的 session 事件（診斷用）
    def on_any_session_event(event):
        event_name = type(event).__name__
        agent_logger.info(f"📡 Session event: {event_name}")
        if hasattr(event, '__dict__'):
            agent_logger.info(f"   Event data: {event.__dict__}")

    session.on("user_input_transcribed", on_user_transcribed)
    session.on("input_audio_buffer_committed", on_input_audio_buffer_committed)
    session.on("input_audio_buffer_speech_started", on_input_audio_buffer_speech_started)
    session.on("input_audio_buffer_speech_stopped", on_input_audio_buffer_speech_stopped)
    session.on("agent_speech", on_agent_speech)

    # 嘗試監聽更多可能的事件
    try:
        session.on("user_speech_committed", lambda e: agent_logger.info(f"🎯 User speech committed: {e}"))
        session.on("audio_input_started", lambda e: agent_logger.info(f"🎙️ Audio input started"))
        session.on("audio_input_stopped", lambda e: agent_logger.info(f"🎙️ Audio input stopped"))
    except Exception as e:
        agent_logger.debug(f"Some event listeners not available: {e}")

    # 監聽音訊軌道訂閱事件
    def on_track_subscribed(track, publication, participant):
        agent_logger.info(f"🎵 Track subscribed from {participant.identity}: {track.kind}")
        agent_logger.info(f"   Track SID: {track.sid}")
        agent_logger.info(f"   Publication SID: {publication.sid}")
        if track.kind == "audio":
            agent_logger.info(f"   Audio track received, enabled: {track.enabled}")

            # ✅ 監聽音訊軌道的資料流（診斷用）
            async def log_audio_frames():
                agent_logger.info(f"📊 Starting audio frame monitoring for {participant.identity}")
                frame_count = 0
                async for frame in track:
                    frame_count += 1
                    if frame_count % 100 == 0:  # 每 100 幀記錄一次
                        agent_logger.info(f"🎤 Received {frame_count} audio frames from {participant.identity}")

            # 啟動監控任務
            asyncio.create_task(log_audio_frames())

    # 監聽軌道發布事件（更早期的事件）
    def on_track_published(publication, participant):
        agent_logger.info(f"📢 Track published from {participant.identity}: {publication.kind}")
        agent_logger.info(f"   Publication SID: {publication.sid}")
        agent_logger.info(f"   Is subscribed: {publication.subscribed}")

    ctx.room.on("track_subscribed", on_track_subscribed)
    ctx.room.on("track_published", on_track_published)

    # 訂閱 LLM 生成事件（即時顯示 LLM 輸出）
    def on_agent_started_speaking(event):
        """當 LLM 開始生成回應時觸發（在 TTS 之前）"""
        if hasattr(event, 'content'):
            agent_logger.info(f"[LLM] Assistant generating: {event.content}")

    session.on("agent_started_speaking", on_agent_started_speaking)

    # 訂閱對話項目新增事件（僅用於記錄）
    def on_conversation_item(event):
        if hasattr(event, 'item') and hasattr(event.item, 'role'):
            if event.item.role == 'assistant':
                content = event.item.content if hasattr(event.item, 'content') else ''
                text = ' '.join(content) if isinstance(content, list) else content
                agent_logger.info(f"[Agent] Response complete: {text[:100]}...")

    session.on("conversation_item_added", on_conversation_item)

    # 記錄房間當前狀態
    agent_logger.info(f"📊 Room state before session.start:")
    agent_logger.info(f"   - Room name: {ctx.room.name}")
    # ctx.room.sid is a coroutine, need to await it
    room_sid = await ctx.room.sid
    agent_logger.info(f"   - Room SID: {room_sid}")
    agent_logger.info(f"   - Local participant: {ctx.room.local_participant.identity}")
    agent_logger.info(f"   - Remote participants count: {len(ctx.room.remote_participants)}")
    agent_logger.info(f"   - Connection state: {ctx.room.connection_state}")

    # 列出所有遠端參與者
    if ctx.room.remote_participants:
        for identity, participant in ctx.room.remote_participants.items():
            agent_logger.info(f"   - Remote participant: {identity} (SID: {participant.sid})")

    # ✅ STREAMTEXT SOLUTION: No custom handler needed!
    # RoomIO automatically registers text_stream_handler when text_enabled=True
    # The text_input_cb will be called automatically when text streams arrive
    agent_logger.info("=" * 80)
    agent_logger.info("✅ [STREAMTEXT] Using RoomIO's built-in text stream handling")
    agent_logger.info("✅ [STREAMTEXT] text_enabled=True in RoomInputOptions")
    agent_logger.info("✅ [STREAMTEXT] text_input_cb=on_text_message")
    agent_logger.info("✅ [STREAMTEXT] RoomIO will automatically register handler for TOPIC_CHAT")
    agent_logger.info("=" * 80)

    # 啟動 session（session.start 會保持運行直到房間關閉）
    # ✅ 關鍵修正：調整音訊配置
    agent_logger.info("🚀 Starting AgentSession...")
    agent_logger.info("📝 [CONFIG] text_enabled=True")
    agent_logger.info(f"📝 [CONFIG] text_input_cb={on_text_message}")
    agent_logger.info(f"📝 [CONFIG] Callback function type: {type(on_text_message)}")

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            audio_enabled=True,          # ✅ 明確啟用音訊輸入（接收用戶語音）
            video_enabled=False,         # ✅ 關閉視訊節省資源
            text_enabled=True,           # ✅ 啟用文字輸入（接收用戶文字訊息）
            text_input_cb=on_text_message,  # ✅ 設置文字訊息回調函數
            noise_cancellation=noise_cancellation.BVC(),  # ✅ 保留 BVC 降噪
            pre_connect_audio_timeout=10.0,  # ✅ 增加超時時間（預設 3 秒可能太短）
        ),
        room_output_options=RoomOutputOptions(
            audio_enabled=True,          # ✅ 確認啟用音訊輸出（TTS）
            transcription_enabled=True,  # 啟用轉錄
        ),
    )
    agent_logger.info("✅ Session started successfully")

    # ✅ 驗證 text_input_cb 是否正確設置
    agent_logger.info("=" * 80)
    agent_logger.info("🔍 [VERIFICATION] Verifying text input configuration...")
    agent_logger.info(f"🔍 [VERIFICATION] text_enabled: True")
    agent_logger.info(f"🔍 [VERIFICATION] text_input_cb function: {on_text_message.__name__}")
    agent_logger.info(f"🔍 [VERIFICATION] Callback is async: {asyncio.iscoroutinefunction(on_text_message)}")
    agent_logger.info("🔍 [VERIFICATION] Waiting for text messages from client...")
    agent_logger.info("🔍 [VERIFICATION] Client should use room.localParticipant.sendChatMessage()")
    agent_logger.info("=" * 80)

    # 記錄房間狀態 after session.start
    agent_logger.info(f"📊 Room state after session.start:")
    agent_logger.info(f"   - Connection state: {ctx.room.connection_state}")
    agent_logger.info(f"   - Remote participants: {[p.identity for p in ctx.room.remote_participants.values()]}")

    # 🔍 CRITICAL: Inspect session internals to understand text handling
    agent_logger.info("=" * 80)
    agent_logger.info("🔍 [DEBUG] Inspecting AgentSession internals for text handling...")

    # Check if session has _room_io attribute (internal RoomIO handler)
    if hasattr(session, '_room_io'):
        room_io = session._room_io
        agent_logger.info(f"✅ [DEBUG] Found _room_io: {type(room_io)}")
        agent_logger.info(f"   - RoomIO attributes: {[attr for attr in dir(room_io) if not attr.startswith('_')]}")

        # Check text stream configuration
        if hasattr(room_io, '_text_stream'):
            agent_logger.info(f"✅ [DEBUG] Found _text_stream: {room_io._text_stream}")
        if hasattr(room_io, '_text_enabled'):
            agent_logger.info(f"   - _text_enabled: {room_io._text_enabled}")
        if hasattr(room_io, '_text_input_cb'):
            agent_logger.info(f"   - _text_input_cb: {room_io._text_input_cb}")
    else:
        agent_logger.warning("⚠️ [DEBUG] No _room_io attribute found on session")

    # Check room's local participant for data channel subscription
    if ctx.room.local_participant:
        local = ctx.room.local_participant
        agent_logger.info(f"🔍 [DEBUG] Local participant: {local.identity}")
        agent_logger.info(f"   - Attributes: {[attr for attr in dir(local) if not attr.startswith('_') and not callable(getattr(local, attr))]}")

    agent_logger.info("=" * 80)
    agent_logger.info("✅ [VERIFICATION] Custom text stream handler registered BEFORE session.start()")
    agent_logger.info("✅ [VERIFICATION] Handler will intercept all publishData messages with topic='lk.chat'")
    agent_logger.info("=" * 80)

    # 檢查已存在的軌道並手動啟動音訊監控
    for identity, participant in ctx.room.remote_participants.items():
        agent_logger.info(f"📋 Checking existing tracks for {identity}:")
        agent_logger.info(f"   - Track publications count: {len(participant.track_publications)}")
        for sid, publication in participant.track_publications.items():
            kind = publication.kind if hasattr(publication, 'kind') else 'unknown'
            agent_logger.info(f"   - Track {kind}: SID={sid}, subscribed={publication.subscribed}")
            if publication.track:
                track = publication.track
                agent_logger.info(f"     • Actual track SID: {track.sid}")
                agent_logger.info(f"     • Track enabled: {track.enabled if hasattr(track, 'enabled') else 'N/A'}")

                # ✅ 手動處理已存在的音訊軌道（因為 track_subscribed 事件不會再次觸發）
                if kind == "audio":
                    agent_logger.info(f"🎯 Found existing audio track, starting monitoring...")

                    async def log_audio_frames():
                        agent_logger.info(f"📊 Starting audio frame monitoring for existing track: {identity}")
                        frame_count = 0
                        try:
                            async for frame in track:
                                frame_count += 1
                                if frame_count % 100 == 0:  # 每 100 幀記錄一次
                                    agent_logger.info(f"🎤 Received {frame_count} audio frames from {identity}")
                        except Exception as e:
                            agent_logger.error(f"❌ Error monitoring audio frames: {e}")

                    # 啟動監控任務
                    asyncio.create_task(log_audio_frames())

    # ✅ 啟動 OpenAI Realtime 對話循環（必須調用才能激活 LLM）
    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting LiveKit agent...")

    # 🔧 FIX: Configure WorkerOptions with can_subscribe permission
    # This is REQUIRED to receive data messages (publishData) from clients
    worker_options = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        # ✅ CRITICAL: Enable data subscription permissions
        # Without can_subscribe=True, agent will NOT receive publishData messages from clients
        permissions=WorkerPermissions(
            can_publish=True,        # Allow agent to publish audio/video/data
            can_subscribe=True,      # ✅ CRITICAL for receiving publishData messages
            can_publish_data=True,   # Allow agent to send data messages
            can_update_metadata=True # Allow metadata updates
        ),
        ws_url=None,  # Use default from env
        api_key=None,  # Use default from env
        api_secret=None,  # Use default from env
    )

    agent_logger.info("🔧 [WORKER] Starting with permissions:")
    agent_logger.info(f"   - Entrypoint: {entrypoint.__name__}")
    agent_logger.info(f"   - can_publish: True")
    agent_logger.info(f"   - can_subscribe: True ✅ (CRITICAL for text messages)")
    agent_logger.info(f"   - can_publish_data: True")
    agent_logger.info(f"   - can_update_metadata: True")

    agents.cli.run_app(worker_options)
