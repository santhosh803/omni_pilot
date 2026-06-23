/* ────────────────────────────────────────────────────────────
   OmniPilot AI — API helpers
   ──────────────────────────────────────────────────────────── */

import type {
  SessionResponse,
  AgentRunResponse,
  ApprovalResponse,
} from "./types";

const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ── Sessions ───────────────────────────────────────────── */

export function createSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/sessions/", {
    method: "POST",
    body: JSON.stringify({ user_id: null }),
  });
}

export function listSessions(): Promise<SessionResponse[]> {
  return request<SessionResponse[]>("/sessions/");
}
export function getSession(id: string): Promise<SessionResponse> {
  return request<SessionResponse>(`/sessions/${id}`);
}

export function deleteSession(id: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/sessions/${id}`, {
    method: "DELETE",
  });
}

/* ── Runs ───────────────────────────────────────────────── */

export function triggerRun(
  sessionId: string,
  query: string
): Promise<AgentRunResponse> {
  return request<AgentRunResponse>(`/sessions/${sessionId}/runs`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

/* ── Approvals ──────────────────────────────────────────── */

export function getPendingApprovals(): Promise<ApprovalResponse[]> {
  return request<ApprovalResponse[]>("/approvals/pending");
}

export function respondApproval(
  id: string,
  approve: boolean
): Promise<ApprovalResponse> {
  return request<ApprovalResponse>(`/approvals/${id}/respond`, {
    method: "POST",
    body: JSON.stringify({ approve }),
  });
}
