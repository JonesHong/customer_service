# from dotenv import load_dotenv
from pathlib import Path
import sys
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    google,
    openai,
    noise_cancellation,
)
from livekit.agents import mcp as mcp_client
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION

# load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                voice="cedar",
                temperature=0.8,
            ),
            # ✅ 關鍵：連到本地或遠端 MCP Server；可並列多個
            mcp_servers=[
                # 1) 若使用 stdio 啟動（同機、以 subprocess 方式）：
                # mcp_client.MCPServerStdio(
                #     command=sys.executable,
                #     args=[str(Path(__file__).with_name("mcp_server.py"))]
                # ),
                # 2) 若使用 HTTP/SSE 方式（請替換 URL 為你的部署位置）：
                # mcp_client.MCPServerHTTP("http://localhost:8000"),
                mcp_client.MCPServerHTTP("http://localhost:9000/sse"),
                # 3) 亦可使用 Streamable HTTP（視伺服器型態而定）
                # mcp_client.MCPServerStreamableHTTP("http://localhost:8000"),
            ],
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
    )

    await ctx.connect()

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
