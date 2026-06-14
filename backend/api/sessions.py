from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from typing import List

from backend.database.config import get_db
from backend.database import crud
from backend.schemas import agent as schemas
from backend.workflows.agent_graph import compiled_graph

router = APIRouter(prefix="/sessions", tags=["Sessions"])

def serialize_messages(messages):
    serialized = []
    for msg in messages:
        # Check standard properties of BaseMessage
        role = "human" if isinstance(msg, HumanMessage) else "ai"
        serialized.append({
            "role": role,
            "content": msg.content,
            "name": getattr(msg, "name", None)
        })
    return serialized

@router.post("/", response_model=schemas.SessionResponse)
async def create_new_session(
    session_data: schemas.SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    session = await crud.create_session(db, user_id=session_data.user_id)
    return session

@router.get("/{session_id}", response_model=schemas.SessionResponse)
async def get_session_details(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/runs", response_model=schemas.AgentRunResponse)
async def trigger_agent_run(
    session_id: int,
    run_data: schemas.AgentRunCreate,
    db: AsyncSession = Depends(get_db)
):
    # Verify session exists
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Log the overall user request as a task
    await crud.create_task(db, session_id=session_id, description=run_data.query)
    
    # Initialize the AgentRun db entry
    run = await crud.create_agent_run(db, session_id=session_id, agent_type="supervisor")
    
    try:
        # Execute the LangGraph workflow
        initial_state = {
            "messages": [HumanMessage(content=run_data.query)],
            "next": "supervisor"
        }
        
        # Run graph to completion
        final_state = await compiled_graph.ainvoke(initial_state)
        
        # Serialize the message history to save in DB state
        serialized_messages = serialize_messages(final_state.get("messages", []))
        
        state_data = {
            "messages": serialized_messages,
            "next": final_state.get("next")
        }
        
        # Update the run status in database
        updated_run = await crud.update_agent_run_status(
            db, 
            run_id=run.id, 
            status="completed", 
            state=state_data
        )
        return updated_run
        
    except Exception as e:
        # Mark agent run as failed in database
        await crud.update_agent_run_status(
            db, 
            run_id=run.id, 
            status="failed", 
            state={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Agent workflow failed: {str(e)}")
