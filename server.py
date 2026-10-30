from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from calendar_client import get_calendar

mcp = FastMCP("morning-agent")
TZ = ZoneInfo("Asia/Beirut")


# ---------- Output shapes ----------

class Event(BaseModel):
    title: str
    start: str       # "2026-10-31" or "2026-11-03T10:30:00+02:00"
    all_day: bool    # all-day events are usually deadlines

class CreatedEvent(BaseModel):
    title: str
    start: str
    link: str        # link to open the event in Google Calendar

class MorningBrief(BaseModel):
    today: str
    deadlines: list[Event]
    meetings_today: list[Event]
    focus_block: CreatedEvent | None
    message: str


# ---------- Tool 1: DATA ----------

def get_upcoming_events(days_ahead: int = 7) -> list[Event]:
    """DATA TOOL. List the events in the user's Google Calendar from now
    until `days_ahead` days from now (1 to 60). Read-only: changes nothing.
    All-day events are usually deadlines; timed events are meetings."""
    if not 1 <= days_ahead <= 60:
        raise ToolError("days_ahead must be between 1 and 60.")
    now = datetime.now(timezone.utc)
    try:
        result = get_calendar().events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=days_ahead)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        raise ToolError(f"Could not reach Google Calendar: {e}")

    events = []
    for e in result.get("items", []):
        all_day = "date" in e["start"]
        events.append(Event(
            title=e.get("summary", "(no title)"),
            start=e["start"]["date"] if all_day else e["start"]["dateTime"],
            all_day=all_day,
        ))
    return events


# ---------- Tool 2: ACTION ----------

def add_task(title: str, start: str, duration_minutes: int = 60) -> CreatedEvent:
    """ACTION TOOL. Add ONE task to the user's Google Calendar.
    `start` is Beirut local time: "2026-11-02T14:00" for a timed task,
    or "2026-11-02" for an all-day deadline (duration is then ignored).
    Refuses dates in the past."""
    if not title.strip():
        raise ToolError("The task needs a title.")

    # 1. Read the date
    try:
        if len(start) == 10:                      # "2026-11-02" = all-day
            day, begin = date.fromisoformat(start), None
        else:                                     # "2026-11-02T14:00" = timed
            begin = datetime.fromisoformat(start)
            if begin.tzinfo is None:
                begin = begin.replace(tzinfo=TZ)
    except ValueError:
        raise ToolError('Bad date. Use "2026-11-02T14:00" or "2026-11-02".')

    # 2. Check it, and build the event
    if begin is None:
        if day < datetime.now(TZ).date():
            raise ToolError(f"{start} is in the past. Nothing was added.")
        body = {"summary": title,
                "start": {"date": day.isoformat()},
                "end": {"date": (day + timedelta(days=1)).isoformat()}}
    else:
        if begin < datetime.now(TZ):
            raise ToolError(f"{start} is in the past. Nothing was added.")
        if not 5 <= duration_minutes <= 720:
            raise ToolError("duration_minutes must be between 5 and 720.")
        end = begin + timedelta(minutes=duration_minutes)
        body = {"summary": title,
                "start": {"dateTime": begin.isoformat()},
                "end": {"dateTime": end.isoformat()}}

    # 3. Save it
    try:
        created = get_calendar().events().insert(
            calendarId="primary", body=body).execute()
    except Exception as e:
        raise ToolError(f"Could not reach Google Calendar: {e}")
    return CreatedEvent(title=title, start=start,
                        link=created.get("htmlLink", ""))


# ---------- Tool 3: ORCHESTRATION ----------

def morning_brief(focus_minutes: int = 120) -> MorningBrief:
    """ORCHESTRATION TOOL. Build the user's morning brief. It (1) calls
    get_upcoming_events for the next 7 days, (2) picks the closest all-day
    deadline, and (3) calls add_task to book one focus block for it at the
    next full hour (or tomorrow 09:00 if it's late). Never books the same
    focus block twice."""
    now = datetime.now(TZ)
    today = now.date().isoformat()

    # Step 1: use the data tool
    events = get_upcoming_events(days_ahead=7)
    deadlines = [e for e in events if e.all_day]
    meetings_today = [e for e in events if not e.all_day and e.start.startswith(today)]

    if not deadlines:
        return MorningBrief(today=today, deadlines=[], meetings_today=meetings_today,
                            focus_block=None,
                            message="No deadlines in the next 7 days. Nothing booked.")

    # Step 2: pick the closest deadline (the list is already sorted by date)
    urgent = deadlines[0]
    focus_title = f"Focus: {urgent.title}"

    # Pick a time: next full hour, or tomorrow 9am if it's late
    slot = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    if slot.hour >= 21 or slot.date() != now.date():
        slot = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    # Don't book twice
    if any(e.title == focus_title for e in events):
        return MorningBrief(today=today, deadlines=deadlines, meetings_today=meetings_today,
                            focus_block=None,
                            message=f"Closest deadline: {urgent.title} ({urgent.start}). "
                                    "A focus block is already booked.")

    # Step 3: use the action tool
    block = add_task(title=focus_title,
                     start=slot.strftime("%Y-%m-%dT%H:%M"),
                     duration_minutes=focus_minutes)

    return MorningBrief(
        today=today, deadlines=deadlines, meetings_today=meetings_today,
        focus_block=block,
        message=f"{len(deadlines)} deadline(s) this week. Closest: {urgent.title} "
                f"({urgent.start}). Booked {focus_minutes} min at {slot:%a %H:%M}.")


# ---------- Register the 3 tools with the MCP server ----------

mcp.tool(get_upcoming_events)
mcp.tool(add_task)
mcp.tool(morning_brief)

if __name__ == "__main__":
    mcp.run()