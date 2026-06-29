from datetime import datetime, timedelta

import pytest

from backend.services.calendar_service import (
    MOCK_CALENDAR_EVENTS,
    check_availability,
    create_event,
    get_events,
)


@pytest.mark.unit
async def test_mock_create_event():
    """Creating an event in mock mode appends to the in-memory store."""
    MOCK_CALENDAR_EVENTS.clear()
    start = datetime(2026, 7, 1, 10, 0)
    event = await create_event(title="Test Sync", start_time=start, duration_minutes=30)
    assert event["title"] == "Test Sync"
    assert event["duration"] == 30
    assert event["start_time"] == start
    assert event["end_time"] == start + timedelta(minutes=30)
    assert len(MOCK_CALENDAR_EVENTS) == 1


@pytest.mark.unit
async def test_mock_availability_overlap():
    """check_availability detects overlapping events in the mock store."""
    MOCK_CALENDAR_EVENTS.clear()
    start = datetime(2026, 7, 1, 10, 0)
    await create_event(title="Blocked", start_time=start, duration_minutes=60)
    # Overlapping request
    assert await check_availability(start, start + timedelta(minutes=30)) is False
    # Non-overlapping request
    later = datetime(2026, 7, 1, 12, 0)
    assert await check_availability(later, later + timedelta(minutes=30)) is True


@pytest.mark.unit
async def test_mock_create_event_conflict_raises():
    """Creating an event on a booked slot raises ValueError."""
    MOCK_CALENDAR_EVENTS.clear()
    start = datetime(2026, 7, 1, 10, 0)
    await create_event(title="First", start_time=start, duration_minutes=60)
    with pytest.raises(ValueError, match="already booked"):
        await create_event(title="Second", start_time=start, duration_minutes=30)


@pytest.mark.unit
async def test_mock_get_events():
    """get_events returns the current contents of the mock store."""
    MOCK_CALENDAR_EVENTS.clear()
    start = datetime(2026, 7, 1, 10, 0)
    await create_event(title="Read Test", start_time=start, duration_minutes=45)
    events = await get_events()
    assert len(events) == 1
    assert events[0]["title"] == "Read Test"
