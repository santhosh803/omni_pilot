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
        
        # Trigger run (should interrupt at calendar node)
        response = client.post(
            f"/api/sessions/{session_id}/runs", 
            json={"query": "Schedule a meeting with the client."}
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
        assert my_approval["action_type"] == "execute_calendar"
        
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
        
        # Trigger run (should run to completion without interrupting)
        response = client.post(
            f"/api/sessions/{session_id}/runs", 
            json={"query": "Prepare a deep research report on AI agent trends."}
        )
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"
        state = run["state"]
        
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


def test_list_sessions():
    print("Evaluating GET /api/sessions/ endpoint...")
    with TestClient(app) as client:
        # Create a few sessions
        created_ids = []
        for _ in range(3):
            res = client.post("/api/sessions/", json={})
            assert res.status_code == 200
            created_ids.append(res.json()["id"])
            
        # List sessions
        res = client.get("/api/sessions/")
        assert res.status_code == 200
        sessions = res.json()
        assert len(sessions) >= 3
        
        # Verify that recent sessions contain our newly created sessions
        session_ids = [s["id"] for s in sessions]
        for cid in created_ids:
            assert cid in session_ids
            
        # Verify newest-first ordering (recent sessions first in the list)
        idx_0 = session_ids.index(created_ids[0])
        idx_1 = session_ids.index(created_ids[1])
        idx_2 = session_ids.index(created_ids[2])
        assert idx_2 < idx_1 < idx_0


def test_delete_session():
    print("Evaluating DELETE /api/sessions/{session_id} endpoint...")
    with TestClient(app) as client:
        # Create a session
        res = client.post("/api/sessions/", json={})
        assert res.status_code == 200
        session_id = res.json()["id"]
        
        # Verify it can be retrieved
        res = client.get(f"/api/sessions/{session_id}")
        assert res.status_code == 200
        
        # Delete the session
        res = client.delete(f"/api/sessions/{session_id}")
        assert res.status_code == 200
        assert res.json() == {"success": True}
        
        # Verify it is no longer retrievable
        res = client.get(f"/api/sessions/{session_id}")
        assert res.status_code == 404


def test_calendar_read_no_interrupt():
    print("Evaluating Calendar Read (No Interrupts)...")
    with TestClient(app) as client:
        # Create a session
        response = client.post("/api/sessions/", json={})
        assert response.status_code == 200
        session_id = response.json()["id"]
        
        # Trigger read-only calendar run (should run to completion without interrupting)
        response = client.post(
            f"/api/sessions/{session_id}/runs", 
            json={"query": "What are my scheduled meetings?"}
        )
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"
        
        messages = run["state"].get("messages", [])
        # Ensure calendar agent responded
        calendar_responded = any(msg.get("name") == "calendar" for msg in messages)
        assert calendar_responded is True
