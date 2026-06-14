from fastapi import FastAPI
from dotenv import load_dotenv
from backend.api import sessions, approvals

load_dotenv()

app = FastAPI(
    title="OmniPilot AI",
    description="Autonomous Multi-Agent Executive Assistant API",
    version="0.1.0"
)

app.include_router(sessions.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to OmniPilot AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
