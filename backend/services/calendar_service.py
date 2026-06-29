import os
import random
from datetime import datetime, timedelta, timezone

import httpx

CALCOM_API_KEY = os.getenv("CALCOM_API_KEY", "")
CALCOM_API_BASE = os.getenv("CALCOM_API_BASE", "https://api.cal.com/v2")
CALCOM_EVENT_TYPE_ID = os.getenv("CALCOM_EVENT_TYPE_ID", "")
CALCOM_API_VERSION = os.getenv("CALCOM_API_VERSION", "2024-08-13")

# In-memory mock storage used only when Cal.com is not configured.
MOCK_CALENDAR_EVENTS: list[dict] = []


def _is_calcom_configured() -> bool:
    return bool(CALCOM_API_KEY and CALCOM_API_KEY != "your_calcom_api_key_here")


def _calcom_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {CALCOM_API_KEY}",
        "cal-api-version": CALCOM_API_VERSION,
        "Content-Type": "application/json",
    }


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def check_availability(start_time: datetime, end_time: datetime) -> bool:
    """Returns True when the timeslot does not overlap any existing event."""
    events = await get_events()
    for event in events:
        if (start_time < event["end_time"]) and (end_time > event["start_time"]):
            return False
    return True


async def create_event(title: str, start_time: datetime, duration_minutes: int = 60) -> dict:
    """Creates a calendar event via Cal.com (or the mock store as fallback)."""
    end_time = start_time + timedelta(minutes=duration_minutes)

    if _is_calcom_configured():
        if not CALCOM_EVENT_TYPE_ID:
            raise ValueError(
                "CALCOM_EVENT_TYPE_ID is not configured. It is required to create Cal.com bookings."
            )

        payload = {
            "eventTypeId": int(CALCOM_EVENT_TYPE_ID),
            "start": start_time.astimezone(timezone.utc).isoformat(),
            "end": end_time.astimezone(timezone.utc).isoformat(),
            "attendee": {
                "name": "OmniPilot",
                "email": os.getenv("CALCOM_ATTENDEE_EMAIL", "assistant@omnipilot.ai"),
                "timeZone": "UTC",
            },
            "language": "en",
            "metadata": {"title": title},
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CALCOM_API_BASE}/bookings",
                json=payload,
                headers=_calcom_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            booking = data.get("booking") or data.get("data") or data

        return {
            "id": booking.get("id", ""),
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration_minutes,
            "status": "confirmed",
        }

    # Mock fallback
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
    """Returns upcoming calendar events from Cal.com (or the mock store)."""
    if _is_calcom_configured():
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CALCOM_API_BASE}/bookings",
                params={"status": "upcoming"},
                headers=_calcom_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("bookings") or data.get("data") or []

        events: list[dict] = []
        for item in raw:
            start = _parse_iso(item["start"])
            end = _parse_iso(item["end"])
            events.append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("metadata", {}).get("title", "Event"),
                    "start_time": start,
                    "end_time": end,
                    "duration": int((end - start).total_seconds() // 60),
                    "status": item.get("status", "confirmed"),
                }
            )
        return events

    return MOCK_CALENDAR_EVENTS
