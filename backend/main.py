import sys
import asyncio

# Configure Windows-specific event loop policy for psycopg compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from backend.api import sessions, approvals
from backend.workflows.agent_graph import pool

from backend.services.worker_service import worker_loop

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task processor
    print("Lifespan: Starting background worker task...")
    worker_task = asyncio.create_task(worker_loop())

    # Open connection pool and build checkpointer schema tables
    print("Lifespan: Initializing Postgres checkpointer pool...")
    import backend.workflows.agent_graph as agent_graph
    if agent_graph.pool._closed:
        from psycopg_pool import AsyncConnectionPool
        print("Lifespan: Recreating closed Postgres connection pool...")
        agent_graph.pool = AsyncConnectionPool(
            conninfo=agent_graph.conn_info, 
            max_size=10, 
            kwargs={"autocommit": True}, 
            open=False
        )
        agent_graph.compiled_graph = None
        
    await agent_graph.pool.open()
    await agent_graph.init_compiled_graph()
    yield
    
    # Cancel worker task on shutdown
    print("Lifespan: Stopping background worker task...")
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    
    # Close pool on shutdown
    print("Lifespan: Closing Postgres checkpointer pool...")
    await agent_graph.pool.close()

app = FastAPI(
    title="OmniPilot AI",
    description="Autonomous Multi-Agent Executive Assistant API",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(sessions.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

# Resolve frontend dist path
frontend_dist_path = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
)

# Mount Vite assets directory if it exists
if os.path.exists(frontend_dist_path):
    assets_path = os.path.join(frontend_dist_path, "assets")
    if os.path.exists(assets_path):
        print(f"Server: Mounting static assets folder from {assets_path}...")
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

@app.get("/")
async def root():
    # Try to serve Vite's production index.html first
    if os.path.exists(frontend_dist_path):
        vite_index = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(vite_index):
            with open(vite_index, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
                
    # Fallback to local static/index.html if exists
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
            
    return {"message": "Welcome to OmniPilot AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
