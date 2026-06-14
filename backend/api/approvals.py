from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.config import get_db
from backend.database import crud
from backend.database.models import Approval, AgentRun
from backend.schemas import agent as schemas
from backend.services.agent_service import execute_or_resume_graph

router = APIRouter(prefix="/approvals", tags=["Approvals"])

@router.get("/pending", response_model=List[schemas.ApprovalResponse])
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    approvals = await crud.get_pending_approvals(db)
    return approvals

@router.post("/{approval_id}/respond", response_model=schemas.ApprovalResponse)
async def respond_to_pending_approval(
    approval_id: int,
    action: schemas.ApprovalAction,
    db: AsyncSession = Depends(get_db)
):
    # Retrieve the approval request
    result = await db.execute(select(Approval).filter(Approval.id == approval_id))
    approval = result.scalars().first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request has already been processed")
        
    # Retrieve the associated agent run to find the session ID
    run_result = await db.execute(select(AgentRun).filter(AgentRun.id == approval.agent_run_id))
    agent_run = run_result.scalars().first()
    if not agent_run:
        raise HTTPException(status_code=404, detail="Associated agent run not found")

    # Save user response
    updated_approval = await crud.respond_to_approval(db, approval_id, action.approve)
    
    if action.approve:
        print(f"Approvals: Resuming graph for session {agent_run.session_id} after user approval.")
        try:
            # Resume graph execution (input=None telling it to pick up where it left off)
            await execute_or_resume_graph(
                session_id=agent_run.session_id,
                run_id=agent_run.id,
                db=db,
                user_query=None
            )
        except Exception as e:
            await crud.update_agent_run_status(
                db, 
                run_id=agent_run.id, 
                status="failed", 
                state={"error": f"Error during resume: {str(e)}"}
            )
            raise HTTPException(status_code=500, detail=f"Failed to resume graph: {str(e)}")
    else:
        print(f"Approvals: Session {agent_run.session_id} task execution rejected by user.")
        # Update run status to failed if rejected
        await crud.update_agent_run_status(
            db, 
            run_id=agent_run.id, 
            status="failed", 
            state={"messages": agent_run.state.get("messages", []), "error": "Rejected by human user."}
        )
        
    return updated_approval
