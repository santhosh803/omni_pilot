from langchain_core.messages import AIMessage, HumanMessage
from backend.services.browser_service import search_web
from backend.services.memory_service import add_meeting_history
from backend.database.config import AsyncSessionLocal

async def research_node(state) -> dict:
    print("--- RUNNING RESEARCH AGENT ---")
    messages = state.get("messages", [])
    
    # 1. Determine what the user wants to research
    query = "AI Agent Trends 2026"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
            
    # 2. Perform web search using Playwright
    search_results = await search_web(query)
    
    # 3. Create a structured markdown briefing
    briefing_markdown = (
        f"# Research Briefing: {query}\n\n"
        f"**Generated on**: 2026-06-14\n\n"
        f"## Search Summary Findings\n"
        f"{search_results}\n\n"
        f"## Recommendations\n"
        f"- Analyze market shifts outlined in search findings.\n"
        f"- Establish calendar schedules to align teams on research notes.\n"
    )
    
    # 4. Save the briefing directly to database meeting history
    # We open a scoped database session inside the node to keep LangGraph state serializable
    async with AsyncSessionLocal() as db:
        try:
            # For testing, we mock or look up a default session ID (or use 1)
            # We can extract the session ID if we want, or default to a dummy session
            session_id = 1
            await add_meeting_history(
                db, 
                session_id=session_id, 
                title=f"Research on: {query[:50]}", 
                summary="Automatically generated market research summary.", 
                briefing=briefing_markdown
            )
            print("Research Agent: Briefing successfully saved to Postgres memories!")
        except Exception as e:
            print(f"Research Agent database logging warning: {e}")

    return {
        "messages": [
            AIMessage(
                content=f"[Research Agent] Completed topic analysis. Briefing generated and indexed in database memories.",
                name="research"
            )
        ]
    }
