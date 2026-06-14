from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
from backend.database import crud
from backend.workflows.agent_graph import init_compiled_graph
from backend.services.observability_service import ObservabilityTracker

def serialize_messages(messages):
    serialized = []
    for msg in messages:
        role = "human" if isinstance(msg, HumanMessage) else "ai"
        serialized.append({
            "role": role,
            "content": msg.content,
            "name": getattr(msg, "name", None)
        })
    return serialized

async def execute_or_resume_graph(
    session_id: int, 
    run_id: int, 
    db: AsyncSession, 
    user_query: str = None
) -> dict:
    """Invokes or resumes the LangGraph workflow, logging latency and token counts to audit logs."""
    # 1. Start Observability Tracker (Phase 3)
    tracker = ObservabilityTracker(action_name="run_agent_workflow")
    tracker.start()
    
    config = {"configurable": {"thread_id": str(session_id)}}
    graph = await init_compiled_graph()
    
    # If a user query is provided, it's a new run. Otherwise, we are resuming from interrupt.
    graph_input = {"messages": [HumanMessage(content=user_query)]} if user_query else None
    
    try:
        # Run/Resume graph
        await graph.ainvoke(graph_input, config=config)
        
        # Check current graph state
        state_snapshot = await graph.aget_state(config)
        next_nodes = state_snapshot.next
        
        messages_list = state_snapshot.values.get("messages", []) if state_snapshot.values else []
        serialized_messages = serialize_messages(messages_list)
        
        state_data = {
            "messages": serialized_messages,
            "next": next_nodes[0] if next_nodes else None
        }
        
        extra_details = {
            "session_id": session_id,
            "run_id": run_id,
            "thread_id": str(session_id)
        }
        
        if next_nodes:
            next_node = next_nodes[0]
            print(f"Agent Service: Graph interrupted before executing node '{next_node}'")
            
            # Create approval
            await crud.create_approval(
                db,
                agent_run_id=run_id,
                action_type=f"execute_{next_node}",
                action_details={"message": f"Confirm execution of the {next_node} agent node."}
            )
            await crud.update_agent_run_status(db, run_id=run_id, status="interrupted", state=state_data)
            
            # Save Observability Audit (Status: Interrupted)
            await tracker.log_and_save(
                db=db,
                status="interrupted",
                prompt_text=user_query or "Resume graph execution",
                response_text=str(serialized_messages),
                extra_details=extra_details
            )
        else:
            print("Agent Service: Graph completed execution.")
            await crud.update_agent_run_status(db, run_id=run_id, status="completed", state=state_data)
            
            # Save Observability Audit (Status: Completed)
            await tracker.log_and_save(
                db=db,
                status="success",
                prompt_text=user_query or "Resume graph execution",
                response_text=str(serialized_messages),
                extra_details=extra_details
            )
            
        return state_data
        
    except Exception as e:
        # Save Observability Audit (Status: Failed)
        await tracker.log_and_save(
            db=db,
            status="failed",
            prompt_text=user_query or "Resume graph execution",
            response_text=f"Error: {str(e)}",
            extra_details={"session_id": session_id, "run_id": run_id, "error": str(e)}
        )
        raise e
