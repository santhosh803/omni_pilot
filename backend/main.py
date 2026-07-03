import asyncio
import os
import sys

# Configure Windows-specific event loop policy for psycopg compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api import approvals, sessions, status
from backend.middleware.auth import ApiKeyMiddleware
from backend.services.logger import logger
from backend.services.worker_service import worker_loop

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task processor
    logger.info("Starting background worker task...")
    worker_task = asyncio.create_task(worker_loop())

    # Open connection pool and build checkpointer schema tables
    logger.info("Initializing Postgres checkpointer pool...")
    import backend.workflows.agent_graph as agent_graph

    if agent_graph.pool._closed:
        from psycopg_pool import AsyncConnectionPool

        logger.info("Recreating closed Postgres connection pool...")
        agent_graph.pool = AsyncConnectionPool(
            conninfo=agent_graph.conn_info, max_size=10, kwargs={"autocommit": True}, open=False
        )
        agent_graph.compiled_graph = None

    await agent_graph.pool.open()
    await agent_graph.init_compiled_graph()

    # Pre-resolve Cal.com event slugs -> event type IDs at startup (fail-fast)
    from backend.services.calendar_service import resolve_all_event_types

    try:
        await resolve_all_event_types()
    except Exception as e:
        logger.warning(
            "Cal.com startup slug resolution failed: %s (will retry on first booking)", e
        )

    yield

    # Cancel worker task on shutdown
    logger.info("Stopping background worker task...")
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)

    # Close pool on shutdown
    logger.info("Closing Postgres checkpointer pool...")
    await agent_graph.pool.close()


app = FastAPI(
    title="OmniPilot AI",
    description="Autonomous Multi-Agent Executive Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# Register API key auth middleware (no-op when OMNIPILOT_API_KEY is unset)
app.add_middleware(ApiKeyMiddleware)

app.include_router(sessions.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(status.router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from fastapi.staticfiles import StaticFiles

# Resolve path to frontend/dist
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

# Ensure directory exists to prevent StaticFiles from crashing FastAPI
if not os.path.exists(frontend_dist):
    os.makedirs(frontend_dist, exist_ok=True)
    with open(os.path.join(frontend_dist, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            "<html><body><h1>OmniPilot UI: Run 'npm run build' in frontend directory to build the app.</h1></body></html>"
        )

# Mount static SPA last so explicit routes (e.g. /health, /api/*) are matched first
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
