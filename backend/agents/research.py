import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from backend.agents.research_crew.crew import run_research_crew
from backend.database.config import AsyncSessionLocal
from backend.services.memory_service import add_meeting_history
from backend.services.worker_service import enqueue_background_job


async def bg_save_research_briefing(session_id: int, title: str, summary: str, briefing: str):
    """Background task function executed by the worker queue (Phase 3)."""
    print(
        f"Background Task: Generating vector embeddings and saving briefing for session {session_id}..."
    )
    async with AsyncSessionLocal() as db:
        await add_meeting_history(
            db, session_id=session_id, title=title, summary=summary, briefing=briefing
        )


async def store_in_memory(briefing: str, metadata: dict, session_id: int):
    """Helper to store briefing in pgvector memory using the existing background task worker pattern."""
    query = metadata.get("query", "AI Agent Trends 2026")
    sources_str = ", ".join(metadata.get("sources", []))
    confidence = metadata.get("confidence", 1.0)

    enqueue_background_job(
        bg_save_research_briefing,
        session_id,
        f"Research on: {query[:50]}",
        f"Automatically generated market research summary. Sources: {sources_str}. Confidence: {confidence}",
        briefing,
    )


async def research_node(state) -> dict:
    print("--- RUNNING RESEARCH AGENT (CREWAI) ---")
    messages = state.get("messages", [])
    session_id = state.get("session_id", 0)

    # 1. Determine target topic
    query = "AI Agent Trends 2026"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    # 2. Run synchronous CrewAI crew in a thread to avoid blocking the async event loop
    result = await asyncio.to_thread(run_research_crew, query)

    # 3. Store briefing in pgvector memory using the existing memory service
    await store_in_memory(
        result["briefing"],
        metadata={"sources": result["sources"], "confidence": result["confidence"], "query": query},
        session_id=session_id,
    )

    # 4. Return updated state using the existing state schema + new fields
    return {
        "research_output": result["briefing"],
        "research_sources": result["sources"],
        "research_confidence": result["confidence"],
        "messages": [
            AIMessage(
                content="[Research Agent] Topic analysis complete. Briefing generated and enqueued for background vector indexing.",
                name="research",
            )
        ],
    }
