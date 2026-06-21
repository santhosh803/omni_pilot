# OmniPilot AI
> **Autonomous Multi-Agent Executive Assistant**

OmniPilot AI is a production-grade multi-agent executive assistant system built using **FastAPI**, **LangGraph**, and **PostgreSQL (with pgvector)**. It orchestrates a Supervisor agent that dynamically routes user requests to specialized worker agents (Browser Search, Calendar Scheduling, Research Analysis) with robust Human-in-the-Loop (HITL) gates, semantic vector memory, and automated evaluation metrics.

---

## 🚀 Key Features

* **Multi-Agent Orchestration**: Powered by a central supervisor graph built on **LangGraph** to coordinate workers.
* **CrewAI Research Sub-crew (New)**: Replaces the basic single research node with a 4-agent sequential CrewAI crew (Planner, Crawler, Analyst, Writer) using Groq Llama 70B and Tavily Search to compile deep, multi-source briefings.
* **AI Router (Phase 3)**: Dynamically selects the most cost-effective Groq model (`Llama 70B` for orchestration/research, `Qwen 32B` for web scraping, and `Llama 8B` for simple text processing).
* **Human-in-the-Loop (HITL)**: Workflow pauses at checkpointers using an async Postgres checkpointer (`AsyncPostgresSaver`) before any tool execution (web searches or scheduling), waiting for user approval.
* **Local Semantic Memory (Phase 2)**: Integrates **pgvector** and a local **Ollama** embeddings engine (`nomic-embed-text`) to index user preferences and generated briefings.
* **Out-of-Band Async Workers (Phase 3)**: Offloads heavy computation (like vector embedding generation) to an async-native in-process queue worker.
* **Observability & Auditing**: Tracks latencies, estimates token usage, and logs structured history directly into database audit tables.
* **Evaluation Framework**: Built-in test suite to automate agent routing and execution benchmarks.

---

## 🛠️ Tech Stack

* **Backend**: FastAPI, Uvicorn, Pydantic (V2)
* **Agent Engine**: LangGraph, LangChain, LangChain-Groq, CrewAI, CrewAI-Tools
* **Database**: PostgreSQL (Dockerized `ankane/pgvector` image)
* **ORM & Migrations**: SQLAlchemy (Async Engine + asyncpg), Alembic
* **Embeddings**: Local Ollama (`nomic-embed-text` v1.5)
* **Automation**: Playwright (for web search operations), Tavily Search API

---

## 📐 Graph Architecture

```mermaid
graph TD
    Start([Start]) --> Supervisor{Supervisor}
    Supervisor -->|next = browser| BrowserAgent[Browser Agent]
    Supervisor -->|next = calendar| CalendarAgent[Calendar Agent]
    Supervisor -->|next = research| ResearchAgent[Research Agent]
    Supervisor -->|next = finish| End([End])
    BrowserAgent --> Supervisor
    CalendarAgent --> Supervisor
    ResearchAgent --> Supervisor
```

---

## 📁 Project Structure

```text
omni_pilot/
│
├── backend/
│   ├── main.py               # FastAPI application bootstrapper & lifespans
│   ├── api/                  # API endpoints (sessions, approvals)
│   ├── agents/               # Supervisor, Browser, Calendar, and Research nodes
│   │   └── research_crew/    # [NEW] CrewAI 4-agent sequential research crew package (Planner, Crawler, Analyst, Writer)
│   ├── services/             # Playwright browser search, Cal.com calendar simulation,
│   │                         # AI Router, Observability trackers, and Async background workers
│   ├── database/             # SQLAlchemy configurations & tables
│   ├── schemas/              # Pydantic validation schemas
│   └── workflows/            # LangGraph state machine workflow definitions
│
├── migrations/               # Alembic database migrations
├── tests/                    # Pytest agent evaluation benchmarks
│
├── docker-compose.yml        # PostgreSQL + pgvector Docker configuration
└── run_server.py             # Uvicorn wrapper supporting selector loop policy
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
* **Python**: 3.10
* **Docker Desktop**: Required to run PostgreSQL container.
* **Ollama**: Installed and running locally on port `11434`. Install the embeddings model:
  ```bash
  ollama pull nomic-embed-text
  ```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
DATABASE_URL=postgresql+asyncpg://omnipilot:omnipilot_pass@localhost:5433/omnipilot_db
```

### 3. Install Dependencies
Using **`uv`** (recommended):
```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
playwright install chromium
```
*(Alternatively, use standard `pip` and virtualenv).*

### 4. Database Setup
Start the PostgreSQL + pgvector Docker container:
```bash
docker compose up -d
```
Apply the database migrations:
```bash
alembic upgrade head
```

---

## 🏃 Running the Application

Start the local server wrapper:
```bash
python run_server.py
```
Open **`http://127.0.0.1:8000/docs`** in your browser to interact with the API Swagger documentation.

---

## 🧪 Testing & Evaluation

Run the automated agent evaluation benchmark suite to verify routing accuracy, observability tracking, background task loops, and interrupts:
```bash
pytest tests/test_agent_evaluation.py
```
