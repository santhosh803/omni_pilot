from datetime import datetime
from typing import Any, Optional, List, Sequence

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database.models import AgentRun, Approval, MeetingHistory, Session, Task, User


# --- User Helpers ---
async def get_or_create_default_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).filter(User.username == "default_user"))
    user = result.scalars().first()
    if not user:
        user = User(username="default_user", email="default@omnipilot.ai")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


# --- Session Helpers ---
async def create_session(db: AsyncSession, user_id: int = None) -> Session:
    if not user_id:
        default_user = await get_or_create_default_user(db)
        user_id = default_user.id  # type: ignore

    session = Session(user_id=user_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: int) -> Optional[Session]:
    result = await db.execute(select(Session).filter(Session.id == session_id))
    return result.scalars().first()


# --- Agent Run Helpers ---
async def create_agent_run(db: AsyncSession, session_id: int, agent_type: str) -> AgentRun:
    run = AgentRun(session_id=session_id, agent_type=agent_type, status="running", state={})
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def update_agent_run_status(
    db: AsyncSession, run_id: int, status: str, state: dict = None
) -> Optional[AgentRun]:
    update_data: dict[str, Any] = {"status": status}
    if status in ["completed", "failed"]:
        update_data["completed_at"] = datetime.now()
    if state is not None:
        update_data["state"] = state

    await db.execute(update(AgentRun).where(AgentRun.id == run_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(AgentRun).filter(AgentRun.id == run_id))
    return result.scalars().first()


# --- Task Helpers ---
async def create_task(db: AsyncSession, session_id: int, description: str) -> Task:
    task = Task(session_id=session_id, description=description, status="pending")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task_status(db: AsyncSession, task_id: int, status: str) -> Optional[Task]:
    await db.execute(update(Task).where(Task.id == task_id).values(status=status))
    await db.commit()
    result = await db.execute(select(Task).filter(Task.id == task_id))
    return result.scalars().first()


# --- Approval Helpers ---
async def create_approval(
    db: AsyncSession, agent_run_id: int, action_type: str, action_details: dict
) -> Approval:
    approval = Approval(
        agent_run_id=agent_run_id,
        action_type=action_type,
        action_details=action_details,
        status="pending",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def respond_to_approval(db: AsyncSession, approval_id: int, approve: bool) -> Optional[Approval]:
    status = "approved" if approve else "rejected"
    await db.execute(update(Approval).where(Approval.id == approval_id).values(status=status))
    await db.commit()
    result = await db.execute(select(Approval).filter(Approval.id == approval_id))
    return result.scalars().first()


async def get_pending_approvals(db: AsyncSession) -> Sequence[Approval]:
    result = await db.execute(select(Approval).filter(Approval.status == "pending"))
    return result.scalars().all()


async def delete_session(db: AsyncSession, session_id: int) -> bool:
    from sqlalchemy import delete

    # 1. Fetch the session
    session = await get_session(db, session_id)
    if not session:
        return False

    # 2. Fetch all runs for the session to delete approvals
    run_ids_result = await db.execute(select(AgentRun.id).filter(AgentRun.session_id == session_id))
    run_ids = run_ids_result.scalars().all()
    if run_ids:
        await db.execute(delete(Approval).filter(Approval.agent_run_id.in_(run_ids)))
        await db.execute(delete(AgentRun).filter(AgentRun.id.in_(run_ids)))

    # 3. Delete tasks
    await db.execute(delete(Task).filter(Task.session_id == session_id))

    # 4. Delete meeting history
    await db.execute(delete(MeetingHistory).filter(MeetingHistory.session_id == session_id))

    # 5. Delete the session itself
    await db.delete(session)
    await db.commit()
    return True
