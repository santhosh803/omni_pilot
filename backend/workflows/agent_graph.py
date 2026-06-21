import os
from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.agents.supervisor import get_supervisor_chain
from backend.agents.browser import browser_node
from backend.agents.calendar import calendar_node
from backend.agents.research import research_node
from backend.services.router_service import select_model_for_task

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
conn_info = DATABASE_URL.replace("+asyncpg", "")

# Create the pool config (to be opened on main startup)
pool = AsyncConnectionPool(conninfo=conn_info, max_size=10, kwargs={"autocommit": True}, open=False)

# This will be initialized dynamically during lifespan startup
compiled_graph = None

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    research_output: str
    research_sources: list[str]
    research_confidence: float

async def supervisor_node(state: AgentState) -> dict:
    print("\n--- RUNNING SUPERVISOR ---")
    messages = state.get("messages", [])
    
    # 1. Resolve user query to select the LLM model dynamically (AI Router - Phase 3)
    user_query = "Agent execution request"
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
            
    model_name = select_model_for_task(user_query)
    
    try:
        # Pass chosen model to the chain generator
        chain = get_supervisor_chain(model_name)
        response = await chain.ainvoke({"messages": messages})
        print(f"Supervisor Decision (LLM - {model_name}): next={response.next}, instructions={response.instructions}")
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
            if getattr(last_msg, "name", None) in ["browser", "calendar", "research"]:
                last_agent = last_msg.name

        # Keyword-based routing fallback for initial testing without API keys
        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content.lower()
                break

        # Sequential fallback logic
        if last_agent == "research":
            # If research completed, check if we need to schedule a calendar event
            if any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
                next_node = "calendar"
                instructions = "[Fallback] Research complete. Routing to Calendar Agent to schedule meeting."
            else:
                next_node = "finish"
                instructions = "[Fallback] Task completed successfully by Research Agent."
        elif last_agent == "browser":
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
            # First turn routing heuristics
            if any(kw in last_user_msg for kw in ["research", "briefing", "report", "prepare"]):
                next_node = "research"
                instructions = "[Fallback] Routing to Research Agent to prepare briefings."
            elif any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
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
    elif next_node == "research":
        return "research"
    else:
        return END

# Define graph structure
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("browser", browser_node)
workflow.add_node("calendar", calendar_node)
workflow.add_node("research", research_node)

# Connect edges
workflow.add_edge("browser", "supervisor")
workflow.add_edge("calendar", "supervisor")
workflow.add_edge("research", "supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_next,
    {
        "browser": "browser",
        "calendar": "calendar",
        "research": "research",
        "__end__": END
    }
)

workflow.set_entry_point("supervisor")

async def init_compiled_graph():
    """Dynamically compiles the graph with Checkpointer inside the active event loop."""
    global compiled_graph
    if compiled_graph is None:
        print("Graph: Compiling StateGraph with AsyncPostgresSaver checkpointer...")
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        compiled_graph = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["browser", "calendar", "research"]
        )
    return compiled_graph
