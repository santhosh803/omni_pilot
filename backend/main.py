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
import os

@app.get("/")
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return {"message": "Welcome to OmniPilot AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
