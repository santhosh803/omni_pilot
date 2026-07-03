"""Builds enriched context from RAG memory for agent nodes.

This module bridges the pgvector-backed memory store (memory_service) and the
LangGraph agent nodes, so the supervisor and research agents can leverage past
user preferences and meeting briefings at routing/execution time.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.config import AsyncSessionLocal
from backend.database.models import Session
from backend.services.memory_service import search_relevant_meetings, search_relevant_memories


async def _get_user_id_for_session(db: AsyncSession, session_id: int) -> int:
    """Resolves the user_id for a given session, falling back to 1."""
    result = await db.execute(select(Session).filter(Session.id == session_id))
    session = result.scalars().first()
    return int(session.user_id) if session and session.user_id else 1


async def build_memory_context(query: str, session_id: int) -> str:
    """Fetches relevant user memories and past meeting briefings.

    Returns a formatted context string suitable for injection into an LLM prompt.
    Returns an empty string when no memories are found or when the embedding
    service (Ollama) is unavailable — callers should treat an empty string as
    "no additional context" and proceed normally.
    """
    try:
        async with AsyncSessionLocal() as db:
            user_id = await _get_user_id_for_session(db, session_id)

            memories = await search_relevant_memories(
                db, user_id=user_id, query_text=query, limit=3
            )
            meetings = await search_relevant_meetings(db, query_text=query, limit=3)
    except Exception as e:
        print(f"Memory Context: Failed to retrieve memories (degraded mode): {e}")
        return ""

    # Filter out zero-vector / irrelevant results (content is empty or placeholder)
    memory_lines: list[str] = []
    for mem in memories:
        text = mem.text_chunk or ""
        if not text or text == "0.0":
            continue
        key = mem.key or "preference"
        memory_lines.append(f"  - {key}: {text}")

    meeting_lines: list[str] = []
    for mtg in meetings:
        title = mtg.title or "Untitled"
        summary = mtg.summary or ""
        if not summary:
            continue
        meeting_lines.append(f"  - {title}: {summary}")

    if not memory_lines and not meeting_lines:
        return ""

    parts: list[str] = []
    if memory_lines:
        parts.append("Relevant user preferences from memory:\n" + "\n".join(memory_lines))
    if meeting_lines:
        parts.append("Past meeting briefings that may be relevant:\n" + "\n".join(meeting_lines))

    return "\n\n".join(parts)


async def find_similar_briefing(query: str) -> tuple[str, str] | None:
    """Checks for a past briefing that semantically matches the query.

    Returns (title, briefing) if a strong match is found, otherwise None.
    Used by the research node to skip regeneration when a similar briefing
    was already produced.
    """
    try:
        async with AsyncSessionLocal() as db:
            meetings = await search_relevant_meetings(db, query_text=query, limit=1)
    except Exception as e:
        print(f"Memory Context: Failed to search for similar briefing: {e}")
        return None

    if not meetings:
        return None

    meeting = meetings[0]
    briefing = str(meeting.briefing or "")
    if not briefing or len(briefing) < 100:
        return None

    return str(meeting.title or "Past Briefing"), briefing
