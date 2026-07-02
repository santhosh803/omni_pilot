"""
stream_service.py
-----------------
Async generator that runs the LangGraph workflow via astream_events() and
yields Server-Sent Event (SSE) formatted strings for node-level progress.

SSE event types emitted:
  node_start  – a graph node began executing
  node_end    – a graph node finished executing
  message     – a complete AI/human message was added to graph state
  routing     – supervisor made a routing decision
  interrupt   – graph hit a HITL interrupt (calendar write gate)
  complete    – graph finished successfully
  error       – graph execution raised an exception
"""

import json
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import crud
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


async def stream_agent_execution(
    session_id: int,
    run_id: int,
    db: AsyncSession,
    user_query: str | None = None,
) -> AsyncIterator[str]:
    """
    Async generator that drives the LangGraph workflow and yields SSE strings.

    Yields one or more SSE events per node execution:
      1. node_start  – as a node begins
      2. node_end    – as a node finishes (includes any new messages)
      3. routing     – when the supervisor decides the next destination
      4. interrupt   – when the graph pauses for HITL approval
      5. complete    – when the full graph run finishes
      6. error       – on unexpected exceptions
    """
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
    prev_messages: list = []

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
        next_nodes = state_snapshot.next or []

        # Serialize final message list
        messages_list = (
            state_snapshot.values.get("messages", []) if state_snapshot.values else []
        )
        serialized_messages = [_serialize_message(m) for m in messages_list]

        state_data: dict = {
            "messages": serialized_messages,
            "next": next_nodes[0] if next_nodes else None,
        }
        if state_snapshot.values:
            for key in ("research_output", "research_sources", "research_confidence"):
                if key in state_snapshot.values:
                    state_data[key] = state_snapshot.values[key]

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
            yield _sse("complete", {"status": "completed", "run_id": run_id})

    except Exception as exc:
        await crud.update_agent_run_status(
            db,
            run_id=run_id,
            status="failed",
            state={"error": str(exc)},
        )
        yield _sse("error", {"error": str(exc)})
