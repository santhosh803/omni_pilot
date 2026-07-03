from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database import crud
from backend.database.config import get_db
from backend.database.models import AgentRun, Approval
from backend.schemas import agent as schemas
from backend.services.stream_service import stream_agent_execution

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("/pending", response_model=list[schemas.ApprovalResponse])
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    approvals = await crud.get_pending_approvals(db)
    return approvals


async def _resolve_approval(
    approval_id: int, action: schemas.ApprovalAction, db: AsyncSession
) -> tuple[Approval, AgentRun]:
    """Shared validation + response logic for both streaming and non-streaming endpoints."""
    result = await db.execute(select(Approval).filter(Approval.id == approval_id))
    approval = result.scalars().first()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request has already been processed")

    run_result = await db.execute(select(AgentRun).filter(AgentRun.id == approval.agent_run_id))
    agent_run = run_result.scalars().first()
    if not agent_run:
        raise HTTPException(status_code=404, detail="Associated agent run not found")

    # Save user response
    await crud.respond_to_approval(db, approval_id, action.approve)

    return approval, agent_run


@router.post("/{approval_id}/respond", response_model=schemas.ApprovalResponse)
async def respond_to_pending_approval(
    approval_id: int, action: schemas.ApprovalAction, db: AsyncSession = Depends(get_db)
):
    """Non-streaming approval response — resumes the graph and returns the approval record."""
    approval, agent_run = await _resolve_approval(approval_id, action, db)

    if action.approve:
        print(f"Approvals: Resuming graph for session {agent_run.session_id} after user approval.")
        try:
            from backend.services.stream_service import execute_or_resume_graph

            await execute_or_resume_graph(
                session_id=agent_run.session_id, run_id=agent_run.id, db=db, user_query=None
            )
        except Exception as e:
            await crud.update_agent_run_status(
                db,
                run_id=agent_run.id,
                status="failed",
                state={"error": f"Error during resume: {str(e)}"},
            )
            raise HTTPException(status_code=500, detail=f"Failed to resume graph: {str(e)}") from e
    else:
        print(f"Approvals: Session {agent_run.session_id} task execution rejected by user.")
        await crud.update_agent_run_status(
            db,
            run_id=agent_run.id,
            status="failed",
            state={
                "messages": agent_run.state.get("messages", []) if agent_run.state else [],
                "error": "Rejected by human user.",
            },
        )

    # Re-fetch the updated approval to return
    result = await db.execute(select(Approval).filter(Approval.id == approval_id))
    return result.scalars().first()


@router.post("/{approval_id}/respond/stream")
async def respond_to_pending_approval_stream(
    approval_id: int, action: schemas.ApprovalAction, db: AsyncSession = Depends(get_db)
):
    """Streaming approval response — resumes the graph and returns an SSE stream.

    Emits the same SSE event types as the /sessions/{id}/runs/stream endpoint:
    node_start, node_end, message, routing, interrupt, complete, error.

    If the user rejects the approval, a single 'complete' event is emitted and
    the stream closes immediately.
    """
    approval, agent_run = await _resolve_approval(approval_id, action, db)

    if not action.approve:
        # Rejection — mark as failed and emit a single event
        print(f"Approvals: Session {agent_run.session_id} task execution rejected by user.")
        await crud.update_agent_run_status(
            db,
            run_id=agent_run.id,
            status="failed",
            state={
                "messages": agent_run.state.get("messages", []) if agent_run.state else [],
                "error": "Rejected by human user.",
            },
        )

        async def rejection_stream():
            import json

            yield f"event: complete\ndata: {json.dumps({'status': 'rejected', 'run_id': agent_run.id})}\n\n"

        return StreamingResponse(
            rejection_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Approval — resume the graph with SSE streaming
    print(
        f"Approvals: Resuming graph (streaming) for session {agent_run.session_id} after approval."
    )

    return StreamingResponse(
        stream_agent_execution(
            session_id=agent_run.session_id,
            run_id=agent_run.id,
            db=db,
            user_query=None,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
