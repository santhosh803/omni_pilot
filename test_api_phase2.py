import os
import sys
import time
import subprocess
import requests

# Configure Windows-specific event loop policy for psycopg compatibility
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def run_phase2_test():
    print("\n=========================================")
    print("Testing Phase 2: Research -> Calendar Flow with HITL")
    print("=========================================")

    # 1. Start the FastAPI server using run_server.py in a background subprocess
    server_process = subprocess.Popen(
        [sys.executable, "run_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give the server a few seconds to initialize connection pools
    print("Starting local server runner...")
    time.sleep(4)
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        # Check health
        health = requests.get(f"{base_url}/health")
        print(f"Server health status: {health.status_code} - {health.json()}")
        
        # Step 1: Create a session
        print("\n[Step 1] Creating a new session...")
        response = requests.post(f"{base_url}/api/sessions/", json={})
        session = response.json()
        session_id = session["id"]
        print(f"-> Success. Session ID: {session_id}")

        # Step 2: Trigger run (Requires both Research and Calendar scheduling)
        print("\n[Step 2] Triggering agent run (Research and schedule meeting)...")
        response = requests.post(
            f"{base_url}/api/sessions/{session_id}/runs", 
            json={"query": "Prepare a research briefing on AI Agent trends, and schedule a meeting."}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        run = response.json()
        print(f"-> Success. Run ID: {run['id']}, Status: {run['status']}")
        
        # Verify it paused at the Research node
        assert run["status"] == "interrupted", f"Expected 'interrupted', got '{run['status']}'"
        print("-> Confirmed: Graph paused at checkpoint before running Research Agent!")

        # Step 3: Fetch and approve the Research Agent run
        print("\n[Step 3] Approving Research Agent execution...")
        response = requests.get(f"{base_url}/api/approvals/pending")
        approvals = response.json()
        
        research_approval = None
        for appr in approvals:
            if appr["agent_run_id"] == run["id"] and "research" in appr["action_type"]:
                research_approval = appr
                break
                
        assert research_approval is not None, "Could not find research approval request"
        print(f"-> Found Approval ID: {research_approval['id']} ({research_approval['action_type']})")

        # Respond to approval (approve = True) -> Resumes and runs Research, then Supervisor runs and routes to Calendar
        response = requests.post(
            f"{base_url}/api/approvals/{research_approval['id']}/respond", 
            json={"approve": True}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("-> Success. Research approved and resumed.")

        # Give the graph a moment to run Research, return to Supervisor, and hit the next interrupt (Calendar)
        time.sleep(4)

        # Step 4: Fetch and approve the Calendar Agent run
        print("\n[Step 4] Approving Calendar Agent execution...")
        response = requests.get(f"{base_url}/api/approvals/pending")
        approvals = response.json()
        
        calendar_approval = None
        for appr in approvals:
            if appr["agent_run_id"] == run["id"] and "calendar" in appr["action_type"]:
                calendar_approval = appr
                break
                
        assert calendar_approval is not None, "Could not find calendar approval request"
        print(f"-> Found Approval ID: {calendar_approval['id']} ({calendar_approval['action_type']})")

        # Respond to approval (approve = True) -> Resumes and runs Calendar, then finishes
        response = requests.post(
            f"{base_url}/api/approvals/{calendar_approval['id']}/respond", 
            json={"approve": True}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("-> Success. Calendar approved and resumed.")

        time.sleep(2)
        print("\n[E2E Phase 2 Test Complete] Sequential Research -> Calendar flow executed successfully!")

    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        print("\nServer Output (so far):")
        server_process.poll()
        if server_process.returncode is not None:
            stdout, stderr = server_process.communicate()
            print(f"Exit code: {server_process.returncode}")
            print(f"Stderr:\n{stderr}")
            print(f"Stdout:\n{stdout}")
        raise e
    finally:
        print("\nShutting down server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("Server stopped.")

if __name__ == "__main__":
    run_phase2_test()
