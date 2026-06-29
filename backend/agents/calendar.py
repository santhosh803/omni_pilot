from datetime import datetime, timedelta

from langchain_core.messages import AIMessage, HumanMessage

from backend.services.calendar_service import create_event, get_events


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

    # Simple mock time parser for tomorrow at 2 PM
    tomorrow = datetime.now() + timedelta(days=1)
    target_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)

    # Try to extract details from user prompt
    title = "Scheduled Event"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            prompt = msg.content.lower()
            if "restaurant" in prompt or "dinner" in prompt or "lunch" in prompt:
                title = "Dinner reservation details"
            elif "meeting" in prompt:
                title = "Meeting appointment"
            break

    try:
        event = await create_event(title=title, start_time=target_time)
        content = (
            f"[Calendar Agent] Successfully scheduled event:\n"
            f"  - Title: {event['title']}\n"
            f"  - Start: {event['start_time'].strftime('%Y-%m-%d %I:%M %p')}\n"
            f"  - End: {event['end_time'].strftime('%Y-%m-%d %I:%M %p')}"
        )
    except Exception as e:
        content = f"[Calendar Agent] Failed to schedule event: {str(e)}"

    return {"messages": [AIMessage(content=content, name="calendar")]}
