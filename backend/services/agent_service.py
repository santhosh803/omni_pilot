from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
from backend.database import crud
from backend.workflows.agent_graph import init_compiled_graph

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
    """Invokes or resumes the LangGraph workflow, handling HITL checkpoints and database updates."""
    config = {"configurable": {"thread_id": str(session_id)}}
    
    # Resolve the dynamically compiled graph
    graph = await init_compiled_graph()
    
    # If a user query is provided, it's a new run. Otherwise, we are resuming from interrupt.
    graph_input = {"messages": [HumanMessage(content=user_query)]} if user_query else None
    
    # Run/Resume graph
    await graph.ainvoke(graph_input, config=config)
    
    # Check current graph state
    state_snapshot = await graph.aget_state(config)
    next_nodes = state_snapshot.next
    
    # Serialize message history for database state storage
    messages_list = state_snapshot.values.get("messages", []) if state_snapshot.values else []
    serialized_messages = serialize_messages(messages_list)
    
    state_data = {
        "messages": serialized_messages,
        "next": next_nodes[0] if next_nodes else None
    }
    
    if next_nodes:
        # Graph was paused at a checkpoint (HITL Interrupt)
        next_node = next_nodes[0]
        print(f"Agent Service: Graph interrupted before executing node '{next_node}'")
        
        # Create an approval record for the user to respond to
        await crud.create_approval(
            db,
            agent_run_id=run_id,
            action_type=f"execute_{next_node}",
            action_details={"message": f"Confirm execution of the {next_node} agent node."}
        )
        
        # Update run status to 'interrupted'
        await crud.update_agent_run_status(db, run_id=run_id, status="interrupted", state=state_data)
    else:
        # Graph finished successfully
        print("Agent Service: Graph completed execution.")
        await crud.update_agent_run_status(db, run_id=run_id, status="completed", state=state_data)
        
    return state_data
