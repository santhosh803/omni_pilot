from langchain_core.messages import AIMessage, HumanMessage

from backend.services.browser_service import search_web


async def browser_node(state) -> dict:
    print("--- RUNNING BROWSER AGENT ---")
    messages = state.get("messages", [])

    # Extract the original user query to search
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
    # Fall back to the last message content (e.g. supervisor instructions) if no human message
    if not query and messages:
        query = messages[-1].content
    if not query:
        return {
            "messages": [
                AIMessage(content="[Browser Agent] No search query was provided.", name="browser")
            ]
        }

    search_results = await search_web(query)

    return {
        "messages": [
            AIMessage(
                content=f"[Browser Agent] Performed web search.\nResults:\n{search_results}",
                name="browser",
            )
        ]
    }
