# Morning Agent — an MCP productivity toolkit

A personal assistant that reads my Google Calendar, adds tasks to it, and builds a morning brief.
Built for EECE 503P/798S (Assignment C5) with **FastMCP** (the MCP server) and the **OpenAI Agents SDK** (the agent, acting as MCP host and client).

## The three tools

| Tool | Type | What it does | Failure it handles |
|---|---|---|---|
| `get_upcoming_events(days_ahead=7)` | **Data** | Lists calendar events from now to `days_ahead` days ahead. Read-only. All-day events are treated as deadlines. | `days_ahead` outside 1–60; Google Calendar unreachable |
| `add_task(title, start, duration_minutes=60)` | **Action** | Adds one event to the calendar. `start` is `"YYYY-MM-DDTHH:MM"` (timed) or `"YYYY-MM-DD"` (all-day deadline), Beirut time. | Empty title; badly formatted date; date in the past; duration outside 5–720 min; calendar unreachable |
| `morning_brief(focus_minutes=120)` | **Orchestration** | Calls `get_upcoming_events`, picks the closest deadline, then calls `add_task` to book a focus block for it (next full hour, or 09:00 tomorrow if late). | Never books the same focus block twice; returns a clear message when there are no deadlines |

Every tool returns a typed result (Pydantic models) and raises a clear `ToolError` instead of failing silently.

## How it fits together

```
You  ->  agent.py (Host + MCP Client, OpenAI Agents SDK, Gemini model)
              |  MCP over stdio
              v
         server.py (FastMCP server: the 3 tools)
              |
              v
         Google Calendar API
```

`agent.py` prints every tool call (`[agent -> server]`) and result (`[server -> agent]`) so the full round trip is visible.

## Files

- `server.py` — FastMCP server with the three tools
- `calendar_client.py` — shared Google login (OAuth), used by all tools
- `agent.py` — the agent: connects to the server and chats with you
- `test_tools.py` — calls each tool directly, including the failure cases
- `requirements.txt` — Python packages

## Setup

**1. Python environment** (Python 3.11+)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**2. Gemini API key** (free, from https://aistudio.google.com)

Create a file named `.env`:

```
GEMINI_API_KEY=your-key-here
```

The OpenAI Agents SDK talks to Gemini through Google's OpenAI-compatible endpoint, so no OpenAI key is needed.

**3. Google Calendar access**

1. In https://console.cloud.google.com, create a project and enable the **Google Calendar API**.
2. In **Google Auth Platform**, set the audience to **External** and add your Gmail under **Test users**.
3. Under **Clients**, create a **Desktop app** client and download the JSON.
4. Save it as `credentials.json` in this folder.

The first run opens a browser to approve access and saves `token.json`.
`credentials.json`, `token.json` and `.env` are in `.gitignore` and must never be committed.

## Run

Test the tools directly (normal and failure cases):

```bash
python test_tools.py
```

Chat with the agent:

```bash
python agent.py
```

Example session:

```
You: add a task for last Monday at 9am
  [agent -> server] add_task({"title":"Task","start":"2026-10-26T09:00"})
  [server -> agent] 2026-10-26T09:00 is in the past. Nothing was added.
Assistant: I couldn't add the task because 2026-10-26 at 9:00 AM is in the past.
```

Try: `what's coming up this week?`, `add a bike ride tomorrow from 8 to 12`, `good morning`.

## Known limits and next steps

- The "all-day event = deadline" rule is simple: an all-day meeting is also treated as a deadline.
- The focus block doesn't yet avoid clashes with existing meetings.
- Planned: voice input for adding tasks, and deploying the server online.
