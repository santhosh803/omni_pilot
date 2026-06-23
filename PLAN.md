# React + Vite Dashboard Redesign Plan

## Summary
Replace the current inline `backend/static/index.html` dashboard with a React + Vite frontend, while keeping FastAPI as the backend API/server. The redesign will implement the three-column OmniPilot interface, recent sessions sidebar, chat workflow panel, HITL approvals, and research briefing viewer.

## Key Changes
- Add a new frontend app under `frontend/` using:
  - React + Vite
  - TypeScript
  - Lucide React
  - Markdown rendering via `react-markdown`
  - PDF export via `html2pdf.js`
- Keep FastAPI APIs under `/api/...`.
- Add `GET /api/sessions/` in `backend/api/sessions.py` to return the 20 most recent sessions, newest first.
- Update FastAPI static serving so production can serve the Vite build from `frontend/dist`.

## Frontend Implementation
- Build the app as these main React pieces:
  - `App`: owns active session, polling, layout state
  - `SessionSidebar`: New Session, recent sessions, active highlight, system status
  - `ApprovalsPanel`: pending approvals for the active session
  - `ChatPanel`: message/activity feed with bottom-docked query input
  - `BriefingViewer`: markdown report viewer and PDF download
  - `api.ts`: typed fetch helpers for sessions, runs, and approvals
- Use a premium dark visual system:
  - Slate/indigo/violet palette
  - Glass panels, soft borders, subtle glows
  - Responsive three-column desktop layout
  - Stacked mobile layout
- Preserve current behavior:
  - `active_session_id` remains in `localStorage`
  - New session creation still calls `POST /api/sessions/`
  - Agent run execution still calls `POST /api/sessions/{id}/runs`
  - Approval actions still call `POST /api/approvals/{id}/respond`
  - Briefing PDF export remains client-side

## Backend Integration
- Add a recent sessions CRUD helper or inline query:
  - Query `Session`
  - Order by `created_at.desc()`
  - Limit 20
  - Attach runs for each returned session
- Keep the existing single-session endpoint unchanged.
- In development, run Vite separately and point requests at FastAPI.
- In production, build Vite and serve `frontend/dist/index.html` from FastAPI root.

## Test Plan
- Backend:
  - Add test coverage for `GET /api/sessions/`
  - Verify max 20 sessions
  - Verify newest-first ordering
  - Verify response shape matches `SessionResponse`
  - Run `python -m pytest tests/test_agent_evaluation.py`
- Frontend:
  - Run `npm install`
  - Run `npm run build`
  - Manually verify session creation, session switching, refresh persistence, workflow execution, approvals, briefing rendering, and PDF download.
- Manual app run:
  - FastAPI: `.venv\Scripts\python.exe run_server.py`
  - Frontend dev server: `npm run dev` from `frontend/`

## Assumptions
- Use TypeScript for maintainability.
- Use plain CSS in `frontend/src/styles.css` first, not Tailwind, to avoid expanding tooling unless needed.
- No database migration is required.
- No auth or multi-user filtering is added in this pass; recent sessions reflect the current app’s existing default-user behavior.
