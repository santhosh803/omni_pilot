from langchain_core.messages import AIMessage, HumanMessage
from backend.services.browser_service import search_web
from backend.services.memory_service import add_meeting_history
from backend.services.worker_service import enqueue_background_job
from backend.database.config import AsyncSessionLocal

async def bg_save_research_briefing(session_id: int, title: str, summary: str, briefing: str):
    """Background task function executed by the worker queue (Phase 3)."""
    print(f"Background Task: Generating vector embeddings and saving briefing for session {session_id}...")
    async with AsyncSessionLocal() as db:
        await add_meeting_history(
            db, 
            session_id=session_id, 
            title=title, 
            summary=summary, 
            briefing=briefing
        )

async def research_node(state) -> dict:
    print("--- RUNNING RESEARCH AGENT ---")
    messages = state.get("messages", [])
    
    # 1. Determine target topic
    query = "AI Agent Trends 2026"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
            
    # 2. Perform web search using Playwright
    search_results = await search_web(query)
    
    # 3. Create structured markdown briefing
    briefing_markdown = (
        f"# Research Briefing: {query}\n\n"
        f"**Generated on**: 2026-06-14\n\n"
        f"## Search Summary Findings\n"
        f"{search_results}\n\n"
        f"## Recommendations\n"
        f"- Analyze market shifts outlined in search findings.\n"
        f"- Establish calendar schedules to align teams on research notes.\n"
    )
    
    # 4. Offload the vector embedding generation and database save to background worker (Phase 3)
    session_id = 1  # Simulated session context ID
    enqueue_background_job(
        bg_save_research_briefing, 
        session_id, 
        f"Research on: {query[:50]}", 
        "Automatically generated market research summary.", 
        briefing_markdown
    )

    return {
        "messages": [
            AIMessage(
                content=f"[Research Agent] Topic analysis complete. Briefing generated and enqueued for background vector indexing.",
                name="research"
            )
        ]
    }
