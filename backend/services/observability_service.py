import time

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import crud
from backend.database.models import AuditLog


async def log_audit_event(
    db: AsyncSession, action_name: str, status: str, user_id: int = None, details: dict = None
) -> AuditLog:
    """Writes a structured record to the database audit_logs table."""
    if not user_id:
        try:
            default_user = await crud.get_or_create_default_user(db)
            user_id = default_user.id
        except Exception:
            user_id = None

    audit_entry = AuditLog(
        user_id=user_id, action_name=action_name, status=status, details=details or {}
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(audit_entry)
    print(f"Observability Audit Log: Saved event '{action_name}' with status '{status}'")
    return audit_entry


class ObservabilityTracker:
    """Helper class to track latency and token metrics for LLM executions."""

    def __init__(self, action_name: str):
        self.action_name = action_name
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start(self):
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    def get_latency(self) -> float:
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 3)
        return 0.0

    def estimate_tokens(self, text: str) -> int:
        """Simple rule-of-thumb: ~4 characters per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    async def log_and_save(
        self,
        db: AsyncSession,
        status: str,
        prompt_text: str = None,
        response_text: str = None,
        extra_details: dict = None,
    ) -> AuditLog:
        self.stop()

        details = extra_details or {}
        details["latency_sec"] = self.get_latency()

        if prompt_text:
            details["prompt_tokens_est"] = self.estimate_tokens(prompt_text)
        if response_text:
            details["response_tokens_est"] = self.estimate_tokens(response_text)

        return await log_audit_event(
            db=db, action_name=self.action_name, status=status, details=details
        )
