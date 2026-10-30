import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.mcp import MCPServerStdio

load_dotenv()                 # reads GEMINI_API_KEY from .env
set_tracing_disabled(True)    # tracing needs an OpenAI key, which we don't use

HERE = os.path.dirname(os.path.abspath(__file__))

# Gemini, reached through its "OpenAI-style" address
gemini = AsyncOpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
model = OpenAIChatCompletionsModel(model="gemini-3.5-flash", openai_client=gemini)


def show_tool_steps(result):
    """Print each tool call, so you can SEE the round trip in the demo."""
    for item in result.new_items:
        if item.type == "tool_call_item":
            print(f"  [agent -> server] {item.raw_item.name}({item.raw_item.arguments})")
        elif item.type == "tool_call_output_item":
            print(f"  [server -> agent] {str(item.output)[:200]}")


async def main():
    # Start server.py and connect to it (this is the MCP client)
    async with MCPServerStdio(
        name="morning-agent",
        params={"command": sys.executable, "args": ["server.py"], "cwd": HERE},
        cache_tools_list=True,
        client_session_timeout_seconds=30,   # Google can be slow
    ) as server:

        agent = Agent(
            name="Morning Assistant",
            model=model,
            mcp_servers=[server],
            instructions=f"""You are Tatiana's morning assistant. You manage her Google Calendar with your tools.
Now is {datetime.now():%A %Y-%m-%d %H:%M}, Beirut time.
- To answer what's coming up, use get_upcoming_events.
- To add a task, use add_task. Turn words like "Saturday 7am" into "YYYY-MM-DDTHH:MM".
  For a deadline with no time, use "YYYY-MM-DD".
- When she says good morning or asks for her brief, use morning_brief.
- If a tool returns an error, say plainly what went wrong. Never pretend it worked.
Keep answers short.""",
        )

        conversation = []
        print("Morning assistant ready. Type 'quit' to stop.")
        while True:
            text = await asyncio.to_thread(input, "\nYou: ")
            if text.strip().lower() in {"quit", "exit"}:
                break
            conversation.append({"role": "user", "content": text})
            result = await Runner.run(agent, conversation)
            show_tool_steps(result)
            print("Assistant:", result.final_output)
            conversation = result.to_input_list()   # remember the chat


asyncio.run(main())