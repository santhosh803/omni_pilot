from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from backend.agents.supervisor import get_supervisor_chain
from backend.agents.browser import browser_node
from backend.agents.calendar import calendar_node

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str

async def supervisor_node(state: AgentState) -> dict:
    print("\n--- RUNNING SUPERVISOR ---")
    messages = state.get("messages", [])
    
    try:
        chain = get_supervisor_chain()
        response = await chain.ainvoke({"messages": messages})
        print(f"Supervisor Decision (LLM): next={response.next}, instructions={response.instructions}")
        return {
            "next": response.next,
            "messages": [AIMessage(content=response.instructions, name="supervisor")]
        }
    except Exception as e:
        print(f"Supervisor warning (Using local keyword routing fallback): {e}")
        
        # Check if an agent has already executed in this turn
        last_agent = None
        if messages:
            last_msg = messages[-1]
            if getattr(last_msg, "name", None) in ["browser", "calendar"]:
                last_agent = last_msg.name

        # Keyword-based routing fallback for initial testing without API keys
        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content.lower()
                break

        # Sequential fallback logic
        if last_agent == "browser":
            # If browser finished, check if calendar is also needed (multi-step prompt)
            if any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
                next_node = "calendar"
                instructions = "[Fallback] Web action complete. Routing to Calendar Agent to schedule."
            else:
                next_node = "finish"
                instructions = "[Fallback] Task completed successfully by Browser Agent."
        elif last_agent == "calendar":
            next_node = "finish"
            instructions = "[Fallback] Task completed successfully by Calendar Agent."
        else:
            # First turn logic
            if any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
                next_node = "calendar"
                instructions = "[Fallback] Routing to Calendar Agent to check/manage calendar schedule."
            elif any(kw in last_user_msg for kw in ["search", "find", "restaurant", "web", "browser", "hotel"]):
                next_node = "browser"
                instructions = "[Fallback] Routing to Browser Agent to perform web search/action."
            else:
                next_node = "finish"
                instructions = "[Fallback] No specific tools needed. Task finished."
            
        print(f"Fallback Supervisor Decision: next={next_node}")
        return {
            "next": next_node,
            "messages": [AIMessage(content=instructions, name="supervisor")]
        }


def route_next(state: AgentState):
    next_node = state.get("next")
    if next_node == "browser":
        return "browser"
    elif next_node == "calendar":
        return "calendar"
    else:
        return END

# Define graph structure
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("browser", browser_node)
workflow.add_node("calendar", calendar_node)

# Connect edges
workflow.add_edge("browser", "supervisor")
workflow.add_edge("calendar", "supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_next,
    {
        "browser": "browser",
        "calendar": "calendar",
        "__end__": END
    }
)

workflow.set_entry_point("supervisor")

compiled_graph = workflow.compile()
