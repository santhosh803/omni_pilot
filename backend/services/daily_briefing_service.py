"""Proactive daily briefing engine.

Runs on a schedule (see backend/main.py), compiles a summary of the day's
Cal.com events, and delivers it as a new OmniPilot session so it's waiting
in the sidebar next time the user opens the app.

v1 scope: schedule summary only, no auto-research per event — the current
Cal.com integration only tracks a single fixed attendee per booking, so
there's no per-event contact/company data to decide what's worth researching.
"""

from datetime import datetime

from backend.database import crud
from backend.database.config import AsyncSessionLocal
from backend.services.calendar_service import get_events


async def generate_daily_briefing_text() -> str:
    """Compiles a plain-text (markdown) summary of today's calendar events."""
    try:
        events = await get_events()
    except Exception as e:
        return f"# Morning Briefing\n\nCouldn't reach the calendar service: {e}"

    today = datetime.now().date()
    todays_events = sorted(
        (ev for ev in events if ev["start_time"].date() == today),
        key=lambda ev: ev["start_time"],
    )

    header = f"# Morning Briefing — {today.strftime('%A, %B %d, %Y')}"

    if not todays_events:
        return f"{header}\n\nNo events scheduled for today. Enjoy the open calendar!"

    lines = [header, "", f"You have {len(todays_events)} event(s) today:", ""]
    for ev in todays_events:
        lines.append(
            f"- **{ev['title']}** — {ev['start_time'].strftime('%I:%M %p')} to "
            f"{ev['end_time'].strftime('%I:%M %p')} ({ev['duration']} min)"
        )
    return "\n".join(lines)


async def run_daily_briefing_job() -> int:
    """Scheduled entry point: compiles today's briefing and delivers it as a new session.

    Returns the id of the created session (useful for tests/manual triggers).
    """
    print("Daily Briefing: Generating morning briefing...")
    briefing = await generate_daily_briefing_text()

    async with AsyncSessionLocal() as db:
        session = await crud.create_session(db)
        run = await crud.create_agent_run(
            db, session_id=int(session.id), agent_type="daily_briefing"
        )
        await crud.update_agent_run_status(
            db,
            run_id=int(run.id),
            status="completed",
            state={
                "messages": [{"role": "ai", "content": briefing, "name": "daily_briefing"}],
            },
        )

    print(f"Daily Briefing: Delivered as session #{session.id}.")
    return int(session.id)
