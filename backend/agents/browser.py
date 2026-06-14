from langchain_core.messages import AIMessage, HumanMessage
from backend.services.browser_service import search_web

async def browser_node(state) -> dict:
    print("--- RUNNING BROWSER AGENT ---")
    messages = state.get("messages", [])
    
    # Extract the original user query to search
    query = "AI agents portfolio project"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
            
    search_results = await search_web(query)
    
    return {
        "messages": [
            AIMessage(
                content=f"[Browser Agent] Performed web search.\nResults:\n{search_results}",
                name="browser"
            )
        ]
    }
