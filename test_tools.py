import asyncio
from datetime import datetime, timedelta
from fastmcp import Client
from server import mcp

async def main():
    async with Client(mcp) as client:

        # --- Tool 1: get_upcoming_events ---
        r = await client.call_tool("get_upcoming_events", {"days_ahead": 7})
        print("Next 7 days:", r.data)

        try:  # failure case: bad input
            await client.call_tool("get_upcoming_events", {"days_ahead": 500})
        except Exception as e:
            print("Expected error:", e)

        # --- Tool 2: add_task ---
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT21:00")
        r = await client.call_tool("add_task", {
            "title": "TEST from morning-agent", "start": tomorrow,
            "duration_minutes": 30})
        print("Added:", r.data)

        try:  # failure case: date in the past
            await client.call_tool("add_task", {"title": "Old", "start": "2020-01-01T10:00"})
        except Exception as e:
            print("Expected error:", e)

        # --- Tool 3: morning_brief ---
        r = await client.call_tool("morning_brief", {})
        print("Brief 1:", r.data.message)

        r = await client.call_tool("morning_brief", {})  # should NOT book again
        print("Brief 2:", r.data.message)

asyncio.run(main())
