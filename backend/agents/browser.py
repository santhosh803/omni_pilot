from langchain_core.messages import AIMessage

async def browser_node(state) -> dict:
    print("--- RUNNING BROWSER AGENT ---")
    # Simulating browser tool execution for Phase 1 Scaffolding
    return {
        "messages": [
            AIMessage(
                content="[Browser Agent] Task processed: Found matching search results on the web.",
                name="browser"
            )
        ]
    }
