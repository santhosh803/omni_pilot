import os
import random
from datetime import datetime, timedelta, timezone

import httpx

CALCOM_API_KEY = os.getenv("CALCOM_API_KEY", "")
CALCOM_API_BASE = os.getenv("CALCOM_API_BASE", "https://api.cal.com/v2")
CALCOM_EVENT_SLUGS = [
    s.strip() for s in os.getenv("CALCOM_EVENT_SLUGS", "15min,30min").split(",") if s.strip()
]
CALCOM_API_VERSION = os.getenv("CALCOM_API_VERSION", "2024-08-13")
CALCOM_ATTENDEE_TIMEZONE = os.getenv("CALCOM_ATTENDEE_TIMEZONE", "Asia/Kolkata")

# In-memory mock storage used only when Cal.com is not configured.
MOCK_CALENDAR_EVENTS: list[dict] = []

# Cached event types resolved from slugs (populated at startup or on first use).
# Each entry: {"id": int, "slug": str, "length": int}
_resolved_event_types: list[dict] = []


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


async def resolve_all_event_types() -> list[dict]:
    """Resolves all configured event slugs to Cal.com event type IDs and durations.

    Uses the cached list when available. Fetches from the Cal.com API on first call
    or when the cache is empty (e.g. after a failed startup resolution).
    """
    global _resolved_event_types

    if _resolved_event_types:
        return _resolved_event_types

    if not _is_calcom_configured():
        raise ValueError("Cal.com is not configured (CALCOM_API_KEY missing).")

    print(f"Calendar Service: Resolving event slugs {CALCOM_EVENT_SLUGS} via Cal.com API...")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CALCOM_API_BASE}/event-types",
            headers=_calcom_headers(),
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    # Cal.com v2 may nest under "event_types" or "data"
    raw_types = data.get("event_types") or data.get("data") or data.get("eventTypes") or []

    resolved: list[dict] = []
    for slug in CALCOM_EVENT_SLUGS:
        matched = None
        for et in raw_types:
            if et.get("slug") == slug:
                matched = et
                break
        if matched:
            resolved.append(
                {
                    "id": int(matched["id"]),
                    "slug": slug,
                    "length": int(matched.get("length", 60)),
                }
            )
            print(
                f"  Resolved '{slug}' -> ID={matched['id']}, length={matched.get('length', 60)}min"
            )
        else:
            print(f"  WARNING: Event type with slug '{slug}' not found in Cal.com account.")

    if not resolved:
        available = [et.get("slug") for et in raw_types if et.get("slug")]
        raise ValueError(
            f"None of the configured slugs {CALCOM_EVENT_SLUGS} were found. "
            f"Available slugs: {available}"
        )

    # Sort by duration ascending so picking is straightforward
    resolved.sort(key=lambda x: x["length"])
    _resolved_event_types = resolved
    return _resolved_event_types


def clear_resolved_event_cache() -> None:
    """Clears the cached event types so the next call re-resolves from the API."""
    global _resolved_event_types
    _resolved_event_types = []


def pick_event_type_for_duration(duration_minutes: int) -> dict:
    """Picks the best event type for the requested duration.

    Strategy: find the smallest event type whose length is >= requested duration.
    If none is large enough, use the largest available.
    """
    import asyncio

    # Try cached list first; if empty, resolve synchronously (blocking fallback)
    event_types = _resolved_event_types
    if not event_types:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context but can't await — caller should have resolved at startup
            raise RuntimeError("Event types not resolved. Call resolve_all_event_types() first.")
        event_types = asyncio.run(resolve_all_event_types())

    for et in event_types:
        if et["length"] >= duration_minutes:
            return et

    # No event type large enough — return the largest available
    return event_types[-1]


async def check_availability(start_time: datetime, end_time: datetime) -> bool:
    """Returns True when the timeslot does not overlap any existing event."""
    events = await get_events()
    for event in events:
        if (start_time < event["end_time"]) and (end_time > event["start_time"]):
            return False
    return True


async def create_event(title: str, start_time: datetime, duration_minutes: int = 30) -> dict:
    """Creates a calendar event via Cal.com (or the mock store as fallback).

    Picks the Cal.com event type whose duration best matches duration_minutes.
    """
    if _is_calcom_configured():
        # Ensure event types are resolved
        await resolve_all_event_types()

        # Pick the best event type for the requested duration
        event_type = pick_event_type_for_duration(duration_minutes)
        actual_duration = event_type["length"]

        print(
            f"Calendar Service: Using event type '{event_type['slug']}' "
            f"(ID={event_type['id']}, {actual_duration}min) for requested {duration_minutes}min"
        )

        end_time = start_time + timedelta(minutes=actual_duration)

        payload = {
            "eventTypeId": event_type["id"],
            "start": start_time.astimezone(timezone.utc).isoformat(),
            "end": end_time.astimezone(timezone.utc).isoformat(),
            "attendee": {
                "name": "OmniPilot",
                "email": os.getenv("CALCOM_ATTENDEE_EMAIL", "assistant@omnipilot.ai"),
                "timeZone": CALCOM_ATTENDEE_TIMEZONE,
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
            "duration": actual_duration,
            "event_type": event_type["slug"],
            "status": "confirmed",
        }

    # Mock fallback
    end_time = start_time + timedelta(minutes=duration_minutes)
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
