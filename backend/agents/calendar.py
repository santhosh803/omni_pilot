from langchain_core.messages import AIMessage

async def calendar_node(state) -> dict:
    print("--- RUNNING CALENDAR AGENT ---")
    # Simulating calendar tool execution for Phase 1 Scaffolding
    return {
        "messages": [
            AIMessage(
                content="[Calendar Agent] Task processed: Event created/updated successfully on Cal.com.",
                name="calendar"
            )
        ]
    }
