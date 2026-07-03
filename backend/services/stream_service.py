"""
stream_service.py
-----------------
Single source of truth for LangGraph workflow execution.

Provides:
  - stream_agent_execution()  — async generator yielding SSE events (used by
    the streaming endpoints for new runs AND approval resumes).
  - execute_or_resume_graph() — thin wrapper that collects all SSE events from
    stream_agent_execution() and returns the final state dict. Used by the
    non-streaming approval endpoint and the non-streaming runs endpoint.

SSE event types emitted:
  node_start  – a graph node began executing
  node_end    – a graph node finished executing
  message     – a complete AI/human message was added to graph state
  routing     – supervisor made a routing decision
  interrupt   – graph hit a HITL interrupt
  complete    – graph finished successfully
  error       – graph execution raised an exception
"""

import json
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import crud
from backend.services.observability_service import ObservabilityTracker
from backend.workflows.agent_graph import init_compiled_graph

# Map LangGraph internal node names to human-readable labels shown in the UI.
NODE_LABELS: dict[str, str] = {
    "supervisor": "Supervisor",
    "browser": "Browser Agent",
    "calendar": "Calendar Agent",
    "calendar_read": "Calendar Agent",
    "research": "Research Agent",
}


def _sse(event_type: str, payload: dict) -> str:
    """Format a single SSE data line."""
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _serialize_message(msg) -> dict:
    """Convert a LangChain message object to a plain dict."""
    role = "human" if isinstance(msg, HumanMessage) else "ai"
    return {"role": role, "content": msg.content, "name": getattr(msg, "name", None)}


def serialize_messages(messages) -> list[dict]:
    """Serialize a list of LangChain messages to plain dicts."""
    return [_serialize_message(m) for m in messages]


def _build_state_data(state_snapshot) -> dict:
    """Extract the serializable state dict from a LangGraph StateSnapshot."""
    next_nodes = state_snapshot.next or []
    messages_list = state_snapshot.values.get("messages", []) if state_snapshot.values else []
    state_data: dict = {
        "messages": serialize_messages(messages_list),
        "next": next_nodes[0] if next_nodes else None,
    }
    if state_snapshot.values:
        for key in ("research_output", "research_sources", "research_confidence"):
            if key in state_snapshot.values:
                state_data[key] = state_snapshot.values[key]
    return state_data


async def stream_agent_execution(
    session_id: int,
    run_id: int,
    db: AsyncSession,
    user_query: str | None = None,
) -> AsyncIterator[str]:
    """Async generator that drives the LangGraph workflow and yields SSE strings.

    This is the single execution path for both new runs and approval resumes.
    When user_query is None, the graph resumes from its last interrupt point.

    Yields SSE events: node_start, node_end, message, routing, interrupt,
    complete, error.
    """
    tracker = ObservabilityTracker(action_name="run_agent_workflow")
    tracker.start()

    config = {"configurable": {"thread_id": str(session_id)}}
    graph = await init_compiled_graph()

    graph_input = (
        {"messages": [HumanMessage(content=user_query)], "session_id": session_id}
        if user_query
        else None
    )

    # Track which nodes we have already emitted a start event for so we don't
    # double-emit on re-entry after an interrupt resume.
    seen_node_starts: set[str] = set()
    # Cache the last observed messages list to detect newly added messages.
    prev_messages: list[dict] = []

    try:
        async for event in graph.astream_events(graph_input, config=config, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")

            # ----------------------------------------------------------------
            # Node start
            # ----------------------------------------------------------------
            if kind == "on_chain_start" and name in NODE_LABELS:
                if name not in seen_node_starts:
                    seen_node_starts.add(name)
                    yield _sse(
                        "node_start",
                        {"node": name, "label": NODE_LABELS[name]},
                    )

            # ----------------------------------------------------------------
            # Node end — inspect the output for new messages / routing info
            # ----------------------------------------------------------------
            elif kind == "on_chain_end" and name in NODE_LABELS:
                output = event.get("data", {}).get("output") or {}

                # Detect new messages added by this node
                new_messages: list[dict] = []
                if isinstance(output, dict):
                    raw_msgs = output.get("messages", [])
                    for msg in raw_msgs:
                        serialized = _serialize_message(msg)
                        if serialized not in prev_messages:
                            prev_messages.append(serialized)
                            new_messages.append(serialized)

                    # Emit routing event when the supervisor node finishes
                    if name == "supervisor":
                        next_dest = output.get("next")
                        if next_dest:
                            label = NODE_LABELS.get(next_dest, next_dest)
                            yield _sse(
                                "routing",
                                {
                                    "from": "supervisor",
                                    "next": next_dest,
                                    "next_label": label,
                                },
                            )

                # Emit message events for each new message
                for msg in new_messages:
                    yield _sse("message", msg)

                yield _sse("node_end", {"node": name, "label": NODE_LABELS[name]})

        # --------------------------------------------------------------------
        # Stream finished — check final graph state for interrupt or completion
        # --------------------------------------------------------------------
        state_snapshot = await graph.aget_state(config)
        state_data = _build_state_data(state_snapshot)
        next_nodes = state_snapshot.next or []
        extra_details = {"session_id": session_id, "run_id": run_id, "thread_id": str(session_id)}

        if next_nodes:
            # HITL interrupt — create approval record
            next_node = next_nodes[0]
            approval = await crud.create_approval(
                db,
                agent_run_id=run_id,
                action_type=f"execute_{next_node}",
                action_details={
                    "message": f"Confirm execution of the {NODE_LABELS.get(next_node, next_node)} agent node."
                },
            )
            await crud.update_agent_run_status(
                db, run_id=run_id, status="interrupted", state=state_data
            )
            await tracker.log_and_save(
                db=db,
                status="interrupted",
                prompt_text=user_query or "Resume graph execution",
                response_text=str(state_data["messages"]),
                extra_details=extra_details,
            )
            yield _sse(
                "interrupt",
                {
                    "node": next_node,
                    "label": NODE_LABELS.get(next_node, next_node),
                    "approval_id": approval.id,
                    "message": f"Waiting for approval before executing {NODE_LABELS.get(next_node, next_node)}.",
                },
            )
        else:
            await crud.update_agent_run_status(
                db, run_id=run_id, status="completed", state=state_data
            )
            await tracker.log_and_save(
                db=db,
                status="success",
                prompt_text=user_query or "Resume graph execution",
                response_text=str(state_data["messages"]),
                extra_details=extra_details,
            )
            yield _sse("complete", {"status": "completed", "run_id": run_id})

    except Exception as exc:
        await crud.update_agent_run_status(
            db,
            run_id=run_id,
            status="failed",
            state={"error": str(exc)},
        )
        await tracker.log_and_save(
            db=db,
            status="failed",
            prompt_text=user_query or "Resume graph execution",
            response_text=f"Error: {str(exc)}",
            extra_details={"session_id": session_id, "run_id": run_id, "error": str(exc)},
        )
        yield _sse("error", {"error": str(exc)})


async def execute_or_resume_graph(
    session_id: int, run_id: int, db: AsyncSession, user_query: str | None = None
) -> dict:
    """Non-streaming wrapper around stream_agent_execution.

    Collects all SSE events from the streaming generator and returns the final
    state dict. This ensures both streaming and non-streaming paths use the
    exact same execution logic (Item 6 unification).
    """
    # Consume the entire stream — the stream function persists state to the DB
    # as it processes interrupt/complete events.
    async for _sse_str in stream_agent_execution(
        session_id=session_id, run_id=run_id, db=db, user_query=user_query
    ):
        pass

    # Fetch the final state from the database (already persisted by the stream)
    from sqlalchemy.future import select

    from backend.database.models import AgentRun

    result = await db.execute(select(AgentRun).filter(AgentRun.id == run_id))
    run = result.scalars().first()
    if run and run.state:
        return dict(run.state)

    return {}
