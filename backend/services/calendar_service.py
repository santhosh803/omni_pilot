import random
from datetime import datetime, timedelta

# In-memory mock storage for calendar events during Phase 1
MOCK_CALENDAR_EVENTS: list[dict] = []


async def check_availability(start_time: datetime, end_time: datetime) -> bool:
    """Simulates checking if a timeslot is free."""
    # Check if there is any overlapping event
    for event in MOCK_CALENDAR_EVENTS:
        if (start_time < event["end_time"]) and (end_time > event["start_time"]):
            return False  # Overlap found
    return True


async def create_event(title: str, start_time: datetime, duration_minutes: int = 60) -> dict:
    """Simulates creating an event on Cal.com."""
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Check availability first
    is_free = await check_availability(start_time, end_time)
    if not is_free:
        raise ValueError(f"Timeslot {start_time} is already booked!")

    event = {
        "id": random.randint(1000, 9999),
        "title": title,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration_minutes,
        "status": "confirmed",
    }
    MOCK_CALENDAR_EVENTS.append(event)
    return event


async def get_events() -> list:
    """Returns all confirmed events."""
    return MOCK_CALENDAR_EVENTS
