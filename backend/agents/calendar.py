import os
import re
from datetime import datetime, timedelta

import dateparser
from dateparser.search import search_dates
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

# Settings for dateparser to interpret relative dates from the user's perspective.
_DPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
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
    """Derives an event title from the user's prompt.

    Strips scheduling-related keywords from the user's request so the title
    reflects the *subject* of the meeting rather than the scheduling instruction.
    """
    lower = prompt.lower()

    # Keyword-based heuristic for common meeting types
    if "restaurant" in lower or "dinner" in lower:
        return "Dinner Reservation"
    if "lunch" in lower:
        return "Lunch Meeting"
    if "standup" in lower or "daily" in lower:
        return "Daily Standup"
    if "client" in lower or "sync" in lower or "call" in lower:
        return "Client Call"
    if "review" in lower:
        return "Review Meeting"
    if "doctor" in lower or "appointment" in lower:
        return "Appointment"

    # Generic fallback: strip scheduling noise and use the remainder as the title
    noise_patterns = [
        r"\b(?:schedule|book|set up|create|add)\b.*?(?:meeting|event|appointment|call|session)\b",
        r"\b(?:for|on|at|tomorrow|today|next|this|on)\b.*",
        r"\b(?:please|can you|i need|i want|help me)\b",
        r"\b\d{1,2}[:\s]?\d{0,2}\s*(?:am|pm)?\b",
        r"\b(?:min|minutes|hour|hours)\b",
    ]
    cleaned = prompt
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Capitalize and truncate
    if cleaned and len(cleaned) > 3:
        return cleaned.title()[:80]

    return "Scheduled Event"


def _extract_datetime(prompt: str) -> datetime:
    """Parses a natural-language datetime from the user's prompt.

    Handles phrases like 'tomorrow at 2 PM', 'next Thursday at 3 PM',
    'Friday morning', 'in 3 hours', 'on Monday at 10:30'.
    Falls back to tomorrow at 2 PM if no date is detected.
    """
    # Two-step approach:
    # 1. Use search_dates to find date/time phrases within the full sentence.
    # 2. Re-parse the extracted phrase with dateparser.parse for accuracy
    #    (search_dates sometimes produces imprecise times for embedded phrases).
    try:
        results = search_dates(prompt, settings=_DPARSER_SETTINGS)
        if results:
            # Filter out duration-like phrases (e.g. "30 min", "1 hour") that
            # search_dates misinterprets as relative time offsets.
            duration_keywords = ("min", "hour", "minute", "hr")
            date_matches = [
                (text, dt)
                for text, dt in results
                if not any(kw in text.lower() for kw in duration_keywords)
            ]
            candidates = date_matches if date_matches else results
            # Take the last candidate's text and re-parse it precisely
            best_text, _ = candidates[-1]
            parsed = dateparser.parse(best_text, settings=_DPARSER_SETTINGS)
            if parsed is not None:
                return parsed
    except Exception:
        pass

    # Fallback: tomorrow at 2 PM
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)


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

    # Also check the supervisor's instructions (last message) for additional context
    supervisor_instructions = ""
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "name") and last_msg.name == "supervisor":
            supervisor_instructions = last_msg.content

    # Combine user prompt and supervisor instructions for parsing
    parse_text = (
        f"{supervisor_instructions} {prompt}".strip() if supervisor_instructions else prompt
    )

    # Parse duration, title, and datetime from the prompt
    duration = _extract_duration(parse_text)
    title = _extract_title(parse_text)
    target_time = _extract_datetime(parse_text)

    # Use the user's timezone from env (matching Cal.com attendee timezone)
    attendee_tz = os.getenv("CALCOM_ATTENDEE_TIMEZONE", "UTC")

    print(
        f"Calendar Agent: Parsed duration={duration}min, title='{title}', "
        f"start={target_time.strftime('%Y-%m-%d %I:%M %p')} (tz={attendee_tz}) from prompt."
    )

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
