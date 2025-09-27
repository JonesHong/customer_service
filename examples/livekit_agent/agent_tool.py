# from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    google,
    openai,
    noise_cancellation,
)
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web

# load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            # llm=google.beta.realtime.RealtimeModel(
            #     voice="Aoede",
            #     temperature=0.8,
            # ),
            # tools=[get_weather, search_web],
            
            llm=openai.realtime.RealtimeModel(
                voice="cedar",  # 預設為 marin, 另提供以下選擇 alloy, ash, ballad, coral, echo, sage, shimmer, verse, cedar
                temperature=0.8,
            ),
            tools=[get_weather, search_web],
        )


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
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



# from livekit.agents import mcp
# # Then pass the MCP server URL to the AgentSession or Agent constructor. The tools will be automatically loaded like any other tool.
# session = AgentSession(
#     #... other arguments ...
#     mcp_servers=[
#         mcp.MCPServerHTTP(
#             "https://your-mcp-server.com"
#         )       
#     ]       
# )
# agent = Agent(
#     #... other arguments ...
#     mcp_servers=[
#         mcp.MCPServerHTTP(
#             "https://your-mcp-server.com"
#         )       
#     ]       
# )