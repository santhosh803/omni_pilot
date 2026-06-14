from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.database.config import get_db
from backend.database import crud
from backend.schemas import agent as schemas

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
    approval = await db.get(crud.Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request has already been processed")
        
    updated_approval = await crud.respond_to_approval(db, approval_id, action.approve)
    return updated_approval
