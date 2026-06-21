from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Message Schemas ---
class MessageSchema(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

# --- Agent Run Schemas ---
class AgentRunCreate(BaseModel):
    query: str

class AgentRunResponse(BaseModel):
    id: int
    session_id: int
    agent_type: str
    status: str
    state: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Session Schemas ---
class SessionCreate(BaseModel):
    user_id: Optional[int] = None

class SessionResponse(BaseModel):
    id: int
    user_id: Optional[int]
    created_at: datetime
    runs: List[AgentRunResponse] = []

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
    action_details: Dict[str, Any]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ApprovalAction(BaseModel):
    approve: bool
