import re
from datetime import datetime, timedelta

from langchain_core.messages import AIMessage, HumanMessage

from backend.services.calendar_service import create_event, get_events

# Word-to-minute mappings for natural language duration extraction
_WORD_DURATIONS = {
    "fifteen": 15,
    "thirty": 30,
    "forty five": 45,
    "forty-five": 45,
    "sixty": 60,
    "ninety": 90,
    "an hour": 60,
    "one hour": 60,
    "half hour": 30,
    "half an hour": 30,
    "quarter hour": 15,
    "quarter of an hour": 15,
    "two hours": 120,
    "three hours": 180,
}


def _extract_duration(prompt: str) -> int:
    """Extracts a meeting duration in minutes from the user's prompt.

    Parses patterns like '30 min', '1 hour', 'half hour', 'fifteen minutes'.
    Falls back to 30 minutes if no duration is detected.
    """
    lower = prompt.lower()

    # 1. Check word-based durations first (longest match first for overlaps)
    for phrase, minutes in sorted(_WORD_DURATIONS.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in lower:
            return minutes

    # 2. Numeric + unit patterns: "30 min", "30 minutes", "30min", "1 hour", "2 hrs"
    # Hours
    hour_match = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\b", lower)
    if hour_match:
        return int(hour_match.group(1)) * 60

    # Minutes
    min_match = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\b", lower)
    if min_match:
        return int(min_match.group(1))

    # 3. Standalone number followed by nothing useful — assume minutes
    num_only = re.search(r"\b(\d{2,3})\s*(?:min|minutes)?\b", lower)
    if num_only and ("min" in lower or "meeting" in lower):
        return int(num_only.group(1))

    # 4. Default fallback
    return 30


def _extract_title(prompt: str) -> str:
    """Derives an event title from the user's prompt."""
    lower = prompt.lower()
    if "restaurant" in lower or "dinner" in lower or "lunch" in lower:
        return "Dinner reservation details"
    if "client" in lower or "sync" in lower or "call" in lower:
        return "Client meeting appointment"
    if "standup" in lower or "daily" in lower:
        return "Daily standup"
    if "review" in lower:
        return "Review meeting"
    return "Scheduled Event"


async def calendar_read_node(state) -> dict:
    print("--- RUNNING CALENDAR READ AGENT ---")
    try:
        events = await get_events()
        if not events:
            content = "[Calendar Agent] Checked calendar. There are no scheduled events."
        else:
            lines = ["[Calendar Agent] Current scheduled events:"]
            for e in events:
                lines.append(
                    f"  - Title: {e['title']}\n"
                    f"    Start: {e['start_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
                    f"    End: {e['end_time'].strftime('%Y-%m-%d %I:%M %p')}"
                )
            content = "\n".join(lines)
    except Exception as e:
        content = f"[Calendar Agent] Failed to retrieve events: {str(e)}"

    return {"messages": [AIMessage(content=content, name="calendar")]}


async def calendar_node(state) -> dict:
    print("--- RUNNING CALENDAR AGENT ---")
    messages = state.get("messages", [])

    # Extract the original user prompt
    prompt = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            prompt = msg.content
            break

    # Parse duration from the prompt (Option B: LLM-driven duration)
    duration = _extract_duration(prompt)
    title = _extract_title(prompt)

    # Simple mock time parser for tomorrow at 2 PM
    tomorrow = datetime.now() + timedelta(days=1)
    target_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)

    print(f"Calendar Agent: Parsed duration={duration}min, title='{title}' from prompt.")

    try:
        event = await create_event(title=title, start_time=target_time, duration_minutes=duration)
        event_type_label = event.get("event_type", f"{event['duration']}min")
        content = (
            f"[Calendar Agent] Successfully scheduled event:\n"
            f"  - Title: {event['title']}\n"
            f"  - Start: {event['start_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
            f"  - End: {event['end_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
            f"  - Duration: {event['duration']} minutes (event type: {event_type_label})"
        )
    except Exception as e:
        content = f"[Calendar Agent] Failed to schedule event: {str(e)}"

    return {"messages": [AIMessage(content=content, name="calendar")]}
