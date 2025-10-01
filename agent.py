# from dotenv import load_dotenv
import logging
from pathlib import Path
import sys
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm, RoomOutputOptions
from livekit.plugins import (
    google,
    openai,
    noise_cancellation,
)
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

# load_dotenv()

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
                voice="cedar",  # 預設為 marin, 另提供以下選擇 alloy, ash, ballad, coral, echo, sage, shimmer, verse, cedar
                temperature=0.8,
                speed=1.5,
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

    async def on_enter(self):
        agent_logger.info("Assistant agent has called when the task is entered")

    async def on_exit(self):
        agent_logger.info("Assistant agent has called when the task is exited.")

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ):
        agent_logger.info(
            f"Called when the user has finished speaking, and the LLM is about to respond. New message: {new_message.text[:50]}..."
        )


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
