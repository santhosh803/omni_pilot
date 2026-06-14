from langchain_core.messages import AIMessage, HumanMessage
from datetime import datetime, timedelta
from backend.services.calendar_service import create_event

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
        
    return {
        "messages": [
            AIMessage(content=content, name="calendar")
        ]
    }
