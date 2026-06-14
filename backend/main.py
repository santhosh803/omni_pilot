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

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open connection pool and build checkpointer schema tables
    print("Lifespan: Initializing Postgres checkpointer pool...")
    await pool.open()
    from backend.workflows.agent_graph import init_compiled_graph
    await init_compiled_graph()
    yield
    # Close pool on shutdown
    print("Lifespan: Closing Postgres checkpointer pool...")
    await pool.close()

app = FastAPI(
    title="OmniPilot AI",
    description="Autonomous Multi-Agent Executive Assistant API",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(sessions.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to OmniPilot AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
