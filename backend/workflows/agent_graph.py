import os
from collections.abc import Sequence
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from psycopg_pool import AsyncConnectionPool

from backend.agents.browser import browser_node
from backend.agents.calendar import calendar_node, calendar_read_node
from backend.agents.research import research_node
from backend.agents.supervisor import get_supervisor_chain
from backend.services.memory_context import build_memory_context
from backend.services.router_service import select_model_for_task

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
conn_info = DATABASE_URL.replace("+asyncpg", "")

# HITL interrupt configuration: which agent nodes require human approval before
# executing. Controlled via the HITL_INTERRUPT_NODES env var (comma-separated).
# Default: only calendar writes are gated. Set to "calendar,browser,research"
# to gate all side-effecting agents.
_default_interrupts = os.getenv("HITL_INTERRUPT_NODES", "calendar")
INTERRUPT_NODES: list[str] = [n.strip() for n in _default_interrupts.split(",") if n.strip()]

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
    session_id: int


def _llm_keys_configured() -> bool:
    """Returns True when at least one LLM provider API key is set (non-placeholder)."""
    groq = os.getenv("GROQ_API_KEY", "")
    if groq and groq != "your_groq_api_key_here":
        return True
    return False


def _keyword_fallback_route(messages: Sequence[BaseMessage]) -> dict:
    """Pure keyword routing used only when no LLM API key is configured."""
    print("Supervisor: No LLM API keys configured — using keyword routing fallback.")

    last_agent = None
    if messages:
        last_msg = messages[-1]
        if getattr(last_msg, "name", None) in ["browser", "calendar", "research"]:
            last_agent = last_msg.name

    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content.lower()
            break

    if last_agent == "research":
        if any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
            next_node = "calendar"
            instructions = (
                "[Fallback] Research complete. Routing to Calendar Agent to schedule meeting."
            )
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
        if any(kw in last_user_msg for kw in ["research", "briefing", "report", "prepare"]):
            next_node = "research"
            instructions = "[Fallback] Routing to Research Agent to prepare briefings."
        elif any(kw in last_user_msg for kw in ["calendar", "schedule", "event", "appointment"]):
            next_node = "calendar"
            instructions = "[Fallback] Routing to Calendar Agent to check/manage calendar schedule."
        elif any(
            kw in last_user_msg
            for kw in ["search", "find", "restaurant", "web", "browser", "hotel"]
        ):
            next_node = "browser"
            instructions = "[Fallback] Routing to Browser Agent to perform web search/action."
        else:
            next_node = "finish"
            instructions = "[Fallback] No specific tools needed. Task finished."

    print(f"Fallback Supervisor Decision: next={next_node}")
    return {"next": next_node, "messages": [AIMessage(content=instructions, name="supervisor")]}


async def supervisor_node(state: AgentState) -> dict:
    print("\n--- RUNNING SUPERVISOR ---")
    messages = state.get("messages", [])
    session_id = state.get("session_id", 0)

    # 1. Resolve user query to select the LLM model dynamically (AI Router)
    user_query = "Agent execution request"
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    # 2. Enrich context with RAG-retrieved user memories and past briefings.
    memory_context = ""
    if session_id:
        memory_context = await build_memory_context(user_query, session_id)
        if memory_context:
            print(f"Supervisor: Injected memory context ({len(memory_context)} chars) into prompt.")

    # 3. If no LLM keys are configured, use the keyword routing fallback.
    if not _llm_keys_configured():
        return _keyword_fallback_route(messages)

    # 4. Invoke the LLM-backed supervisor chain, injecting memory context if available.
    model_name = select_model_for_task(user_query)
    try:
        chain = get_supervisor_chain(model_name)

        # Prepend memory context as a system-level note when available
        enriched_messages = messages
        if memory_context:
            enriched_messages = [
                HumanMessage(
                    content=f"[Context from memory]\n{memory_context}\n\n[User request]\n{user_query}"
                )
            ] + list(messages)

        response = await chain.ainvoke({"messages": enriched_messages})
        print(
            f"Supervisor Decision (LLM - {model_name}): next={response.next}, instructions={response.instructions}"
        )
        return {
            "next": response.next,
            "messages": [AIMessage(content=response.instructions, name="supervisor")],
        }
    except Exception as e:
        # Keys are configured but the LLM call failed — do not silently fall back.
        print(f"Supervisor error (LLM call failed with keys configured): {e}")
        raise


def route_next(state: AgentState):
    next_node = state.get("next")
    if next_node == "browser":
        return "browser"
    elif next_node == "calendar":
        messages = state.get("messages", [])
        is_read = False

        # Check supervisor instructions (last message)
        if messages:
            last_msg = messages[-1]
            content = last_msg.content.lower()
            if any(
                kw in content
                for kw in [
                    "list",
                    "retrieve",
                    "get",
                    "show",
                    "view",
                    "check",
                    "read",
                    "current",
                    "upcoming",
                ]
            ):
                is_read = True

        # Check original human message
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                prompt = msg.content.lower()
                if any(
                    kw in prompt
                    for kw in [
                        "list",
                        "retrieve",
                        "get",
                        "show",
                        "view",
                        "check",
                        "read",
                        "current",
                        "upcoming",
                    ]
                ):
                    is_read = True
                break

        if is_read:
            return "calendar_read"
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
workflow.add_node("calendar_read", calendar_read_node)
workflow.add_node("research", research_node)

# Connect edges
workflow.add_edge("browser", "supervisor")
workflow.add_edge("calendar", "supervisor")
workflow.add_edge("calendar_read", "supervisor")
workflow.add_edge("research", "supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_next,
    {
        "browser": "browser",
        "calendar": "calendar",
        "calendar_read": "calendar_read",
        "research": "research",
        "__end__": END,
    },
)

workflow.set_entry_point("supervisor")


async def init_compiled_graph():
    """Dynamically compiles the graph with Checkpointer inside the active event loop."""
    global compiled_graph
    if compiled_graph is None:
        print(
            f"Graph: Compiling StateGraph with AsyncPostgresSaver checkpointer "
            f"(interrupt_before={INTERRUPT_NODES})..."
        )
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        compiled_graph = workflow.compile(
            checkpointer=checkpointer, interrupt_before=INTERRUPT_NODES
        )
    return compiled_graph
