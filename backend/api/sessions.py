from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database import crud
from backend.database.config import get_db
from backend.database.models import AgentRun, Session
from backend.schemas import agent as schemas
from backend.services.agent_service import execute_or_resume_graph

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("/", response_model=schemas.SessionResponse)
async def create_new_session(
    session_data: schemas.SessionCreate, db: AsyncSession = Depends(get_db)
):
    session = await crud.create_session(db, user_id=session_data.user_id)
    return session


@router.get("/", response_model=list[schemas.SessionResponse])
async def list_recent_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).order_by(Session.created_at.desc()).limit(20))
    sessions = result.scalars().all()

    if sessions:
        session_ids = [s.id for s in sessions]

        runs_result = await db.execute(
            select(AgentRun)
            .filter(AgentRun.session_id.in_(session_ids))
            .order_by(AgentRun.created_at.asc())
        )
        all_runs = runs_result.scalars().all()

        runs_by_session: dict[int, list[AgentRun]] = {}
        for run in all_runs:
            runs_by_session.setdefault(run.session_id, []).append(run)

        for session in sessions:
            session.runs = runs_by_session.get(session.id, [])

    return sessions


@router.get("/{session_id}", response_model=schemas.SessionResponse)
async def get_session_details(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch runs associated with this session
    result = await db.execute(
        select(AgentRun)
        .filter(AgentRun.session_id == session_id)
        .order_by(AgentRun.created_at.asc())
    )
    runs = result.scalars().all()
    session.runs = runs

    return session


@router.post("/{session_id}/runs", response_model=schemas.AgentRunResponse)
async def trigger_agent_run(
    session_id: int, run_data: schemas.AgentRunCreate, db: AsyncSession = Depends(get_db)
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
        # Run graph
        await execute_or_resume_graph(
            session_id=session_id, run_id=run.id, db=db, user_query=run_data.query
        )

        # Retrieve updated agent run entry from database
        result = await db.execute(select(AgentRun).filter(AgentRun.id == run.id))
        return result.scalars().first()

    except Exception as e:
        import traceback

        traceback.print_exc()
        # Mark agent run as failed in database
        await crud.update_agent_run_status(
            db, run_id=run.id, status="failed", state={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Agent workflow failed: {str(e)}") from e
