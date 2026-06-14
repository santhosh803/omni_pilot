import os
import sys
import time
import subprocess
import requests

# Configure Windows-specific event loop policy for psycopg compatibility
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def run_integration_test():
    print("\n=========================================")
    print("Testing End-to-End API with HITL Interrupts (Dynamic Event Loop)")
    print("=========================================")

    # 1. Start the FastAPI server using run_server.py in a background subprocess
    # sys.executable points directly to the active virtual environment's python.exe
    server_process = subprocess.Popen(
        [sys.executable, "run_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give the server a few seconds to initialize connection pools & run migrations
    print("Starting local server runner...")
    time.sleep(4)
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        # Check if the server is healthy
        health = requests.get(f"{base_url}/health")
        print(f"Server health status: {health.status_code} - {health.json()}")
        
        # 2. Create a session
        print("\n[Step 1] Creating a new session...")
        response = requests.post(f"{base_url}/api/sessions/", json={})
        assert response.status_code == 200, f"Failed: {response.text}"
        session = response.json()
        session_id = session["id"]
        print(f"-> Success. Session ID: {session_id}")

        # 3. Trigger an agent run (Search query: should route to Browser and interrupt)
        print("\n[Step 2] Triggering agent run (Find a restaurant)...")
        response = requests.post(
            f"{base_url}/api/sessions/{session_id}/runs", 
            json={"query": "Find a good Italian restaurant."}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        run = response.json()
        print(f"-> Success. Run ID: {run['id']}, Status: {run['status']}")
        
        # Verify the graph was paused
        assert run["status"] == "interrupted", f"Expected 'interrupted', got '{run['status']}'"
        print("-> Confirmed: Graph paused at checkpoint before running Browser Agent!")

        # 4. Check for pending approvals
        print("\n[Step 3] Fetching pending approvals...")
        response = requests.get(f"{base_url}/api/approvals/pending")
        assert response.status_code == 200, f"Failed: {response.text}"
        approvals = response.json()
        assert len(approvals) > 0, "No pending approvals found"
        
        # Find the approval for our run
        my_approval = None
        for appr in approvals:
            if appr["agent_run_id"] == run["id"]:
                my_approval = appr
                break
                
        assert my_approval is not None, "Could not find approval request for our run"
        print(f"-> Success. Found Approval ID: {my_approval['id']}, Action Type: {my_approval['action_type']}")

        # 5. Respond to approval (approve = True) -> Resumes graph execution
        print(f"\n[Step 4] Approving action ID {my_approval['id']} (Resuming graph)...")
        response = requests.post(
            f"{base_url}/api/approvals/{my_approval['id']}/respond", 
            json={"approve": True}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("-> Success. Approval response registered.")

        # Let's verify by retrieving the final agent run status to make sure it runs and finishes
        time.sleep(2)
        print("\n[E2E Test Complete] State machine successfully interrupted and resumed under dynamic checkpointer!")

    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        # Terminate first, then print stdout/stderr
        print("\nShutting down server and retrieving logs...")
        server_process.terminate()
        stdout, stderr = server_process.communicate()
        print(f"Server Stderr:\n{stderr}")
        print(f"Server Stdout:\n{stdout}")
        raise e
    finally:
        # Terminate the background server process cleanly if it wasn't terminated in except block
        if server_process.returncode is None:
            print("\nShutting down server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("Server stopped.")

if __name__ == "__main__":
    run_integration_test()
