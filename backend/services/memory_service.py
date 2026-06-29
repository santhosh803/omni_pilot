import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import MeetingHistory, UserMemory

OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"


async def generate_embedding(text: str) -> list[float]:
    """Calls local Ollama instance to generate 768-dimensional text embedding."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OLLAMA_EMBEDDING_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=10.0
            )
            response.raise_for_status()
            return response.json()["embedding"]
    except Exception as e:
        print(
            f"Ollama Embedding Error (Make sure Ollama is running and has {EMBEDDING_MODEL} installed): {e}"
        )
        # Fallback to a zero-vector of 768-dim if Ollama is not active to prevent crashes
        return [0.0] * 768


async def add_user_memory(
    db: AsyncSession, user_id: int, key: str, value: dict = None, text_chunk: str = None
) -> UserMemory:
    """Generates embedding and stores user preference or general text context."""
    embedding = None
    if text_chunk:
        embedding = await generate_embedding(text_chunk)

    memory = UserMemory(
        user_id=user_id, key=key, value=value, text_chunk=text_chunk, embedding=embedding
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def add_meeting_history(
    db: AsyncSession, session_id: int, title: str, summary: str, briefing: str
) -> MeetingHistory:
    """Stores meeting briefings and indexes them semantically."""
    # Combine title, summary, and briefing for semantic indexing
    indexing_text = f"Title: {title}\nSummary: {summary}\nBriefing:\n{briefing}"
    embedding = await generate_embedding(indexing_text)

    history = MeetingHistory(
        session_id=session_id, title=title, summary=summary, briefing=briefing, embedding=embedding
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


async def search_relevant_memories(
    db: AsyncSession, user_id: int, query_text: str, limit: int = 3
) -> list[UserMemory]:
    """Performs pgvector cosine-distance similarity search to fetch related user preferences."""
    query_vector = await generate_embedding(query_text)

    # SQL query sorting by pgvector cosine similarity distance
    stmt = (
        select(UserMemory)
        .filter(UserMemory.user_id == user_id)
        .order_by(UserMemory.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def search_relevant_meetings(
    db: AsyncSession, query_text: str, limit: int = 3
) -> list[MeetingHistory]:
    """Performs semantic similarity search to locate past meeting briefings."""
    query_vector = await generate_embedding(query_text)

    stmt = (
        select(MeetingHistory)
        .order_by(MeetingHistory.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
