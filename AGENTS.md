# AGENTS.md

Reference for AI agents (and humans) working on this repository.

## Project

OmniPilot AI — autonomous multi-agent executive assistant. FastAPI + LangGraph
backend, React + Vite frontend, PostgreSQL with pgvector.

## Commands

### Backend (run from repo root)

| Task | Command |
|------|---------|
| Install deps | `uv pip install -r requirements.txt` (or `uv sync --extra dev`) |
| Run server | `python run_server.py` |
| Lint | `ruff check backend tests run_server.py` |
| Format | `ruff format backend tests run_server.py` |
| Format check | `ruff format --check backend tests run_server.py` |
| Type-check | `mypy backend tests` |
| Run unit tests | `pytest tests -k "not test_e2e and not test_research_crew and not test_list_sessions" -v` |
| Run all tests | `pytest tests -v` (needs Postgres + pgvector + API keys) |

### Frontend (run from `frontend/`)

| Task | Command |
|------|---------|
| Install deps | `npm install` |
| Dev server | `npm run dev` |
| Build | `npm run build` (runs `tsc -b && vite build`) |
| Lint | `npm run lint` (oxlint) |
| Preview build | `npm run preview` |

### Database

| Task | Command |
|------|---------|
| Start Postgres + pgvector | `docker compose up -d` |
| Apply migrations | `alembic upgrade head` |
| Pull Ollama embeddings | `ollama pull nomic-embed-text` |

### Playwright (for browser agent)

| Task | Command |
|------|---------|
| Install Chromium | `playwright install chromium` |

## Lint/type-check before committing

Always run, in this order:

1. `ruff check backend tests run_server.py` — must pass
2. `ruff format --check backend tests run_server.py` — must pass
3. `mypy backend tests` — must pass
4. `npm run lint` (in `frontend/`) — must pass
5. `npm run build` (in `frontend/`) — must pass

## Architecture notes

- LangGraph state graph: `backend/workflows/agent_graph.py`
- Supervisor routes to `browser`, `calendar`, `calendar_read`, `research` worker nodes
- HITL interrupt: `interrupt_before=["calendar"]` (only calendar writes are gated)
- CrewAI research sub-crew: `backend/agents/research_crew/`
- Async Postgres checkpointer (`AsyncPostgresSaver`) for graph state persistence
- Frontend SPA served by FastAPI `StaticFiles` mount at `/` from `frontend/dist/`

## Known issues (to be addressed in later phases)

- Integration tests (`test_e2e_*`, `test_research_crew_*`, `test_list_sessions`) expect
  interrupts before browser/research nodes, but the current `interrupt_before` config
  only gates calendar. These are skipped in CI until reconciled in Phase 3.
- Calendar service is an in-memory mock (`backend/services/calendar_service.py`).
- `store_in_memory` hardcodes `session_id = 1` (`backend/agents/research.py`).
