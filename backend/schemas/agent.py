from datetime import datetime
from typing import Any

from pydantic import BaseModel


# --- Message Schemas ---
class MessageSchema(BaseModel):
    role: str
    content: str
    name: str | None = None


# --- Agent Run Schemas ---
class AgentRunCreate(BaseModel):
    query: str


class AgentRunResponse(BaseModel):
    id: int
    session_id: int
    agent_type: str
    status: str
    state: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


# --- Session Schemas ---
class SessionCreate(BaseModel):
    user_id: int | None = None


class SessionResponse(BaseModel):
    id: int
    user_id: int | None
    created_at: datetime
    runs: list[AgentRunResponse] = []

    class Config:
        from_attributes = True


# --- Task Schemas ---
class TaskCreate(BaseModel):
    description: str


class TaskResponse(BaseModel):
    id: int
    session_id: int
    description: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Approval Schemas ---
class ApprovalResponse(BaseModel):
    id: int
    agent_run_id: int
    action_type: str
    action_details: dict[str, Any]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalAction(BaseModel):
    approve: bool
