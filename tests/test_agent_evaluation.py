import sys
import os
import asyncio
import pytest
from fastapi.testclient import TestClient

# Configure Windows-specific event loop policy for psycopg compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.services.router_service import select_model_for_task
from backend.services.observability_service import ObservabilityTracker
from backend.services.worker_service import enqueue_background_job, worker_loop, BACKGROUND_QUEUE

# --- 1. AI Router Evaluation Tests (Phase 3) ---
def test_ai_router_eval():
    print("Evaluating AI Router decision logic...")
    
    # Simple classification cases
    assert select_model_for_task("Schedule a meeting for tomorrow.") == "llama-3.1-8b-instant"
    assert select_model_for_task("Summarize my notes.") == "llama-3.1-8b-instant"
    
    # Web/Browser classification cases
    assert select_model_for_task("Search for the nearest restaurant.") == "qwen-2.5-32b"
    assert select_model_for_task("Browse the website and extract details.") == "qwen-2.5-32b"
    
    # Complex planning / research classification cases
    assert select_model_for_task("Prepare a deep market briefing on AI trends.") == "llama-3.3-70b-versatile"
    assert select_model_for_task("Coordinate browser search, then add it to calendar.") == "llama-3.3-70b-versatile"

# --- 2. Observability Metrics Evaluation Tests (Phase 3) ---
def test_observability_tokens_eval():
    print("Evaluating Observability token estimator...")
    tracker = ObservabilityTracker(action_name="test_tokens")
    
    # Simple token assertions (~4 characters per token)
    assert tracker.estimate_tokens("Hello World") == 2
    assert tracker.estimate_tokens("") == 0
    assert tracker.estimate_tokens("A" * 40) == 10

# --- 3. Background Worker Queue Evaluation Tests (Phase 3) ---
@pytest.mark.asyncio
async def test_background_worker_queue_eval():
    print("Evaluating Background Worker processing...")
    
    job_completed = False
    
    async def sample_task():
        nonlocal job_completed
        job_completed = True
        
    # Start worker listener
    worker_task = asyncio.create_task(worker_loop())
    
    # Enqueue job
    enqueue_background_job(sample_task)
    
    # Give it a split second to process from queue
    await asyncio.sleep(0.5)
    
    # Cleanup task
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    
    assert job_completed is True

# --- 4. E2E Checkpoint & HITL Interrupt API Test ---
def test_e2e_hitl_checkpoints():
    print("Evaluating E2E Checkpoints and HITL interrupts...")
    
    with TestClient(app) as client:
        # Create a session
        response = client.post("/api/sessions/", json={})
        assert response.status_code == 200
        session_id = response.json()["id"]
        
        # Trigger run (should interrupt at browser node)
        response = client.post(
            f"/api/sessions/{session_id}/runs", 
            json={"query": "Search for AI news."}
        )
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "interrupted"
        
        # Fetch pending approvals
        response = client.get("/api/approvals/pending")
        assert response.status_code == 200
        approvals = response.json()
        
        my_approval = None
        for appr in approvals:
            if appr["agent_run_id"] == run["id"]:
                my_approval = appr
                break
                
        assert my_approval is not None
        
        # Approve task execution -> resumes graph
        response = client.post(
            f"/api/approvals/{my_approval['id']}/respond", 
            json={"approve": True}
        )
        assert response.status_code == 200


def test_research_crew_quality():
    print("Evaluating Research Crew Quality...")
    
    with TestClient(app) as client:
        # Create a session
        response = client.post("/api/sessions/", json={})
        assert response.status_code == 200
        session_id = response.json()["id"]
        
        # Trigger run (should interrupt before research node)
        response = client.post(
            f"/api/sessions/{session_id}/runs", 
            json={"query": "Prepare a deep research report on AI agent trends."}
        )
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "interrupted"
        
        # Fetch pending approvals
        response = client.get("/api/approvals/pending")
        assert response.status_code == 200
        approvals = response.json()
        
        my_approval = None
        for appr in approvals:
            if appr["agent_run_id"] == run["id"]:
                my_approval = appr
                break
                
        assert my_approval is not None
        assert my_approval["action_type"] == "execute_research"
        
        # Approve task execution -> resumes graph and runs the research node
        response = client.post(
            f"/api/approvals/{my_approval['id']}/respond", 
            json={"approve": True}
        )
        assert response.status_code == 200

        # Query the database to get the updated agent run
        from backend.database.config import AsyncSessionLocal
        from backend.database.models import AgentRun
        from sqlalchemy.future import select
        import asyncio

        async def get_updated_run():
            async with AsyncSessionLocal() as db:
                stmt = select(AgentRun).where(AgentRun.id == run["id"])
                res = await db.execute(stmt)
                return res.scalars().first()

        updated_run = asyncio.run(get_updated_run())
        assert updated_run.status == "completed"
        state = updated_run.state
        
        # Asserts
        assert "research_output" in state
        assert state["research_output"] is not None
        assert len(state["research_output"]) > 0
        
        assert "research_sources" in state
        assert isinstance(state["research_sources"], list)
        assert len(state["research_sources"]) >= 2
        
        assert "research_confidence" in state
        confidence = state["research_confidence"]
        assert isinstance(confidence, (int, float))
        assert 0.0 <= confidence <= 1.0
