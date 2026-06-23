/* ────────────────────────────────────────────────────────────
   OmniPilot AI — shared type definitions
   ──────────────────────────────────────────────────────────── */

export interface Message {
  role: "human" | "ai" | "tool" | "system";
  content: string;
  name?: string;
}

export interface AgentRunState {
  messages?: Message[];
  research_output?: string;
  research_sources?: string[];
  research_confidence?: number;
}

export interface AgentRunResponse {
  id: string;
  session_id: string;
  agent_type: string;
  status: "pending" | "running" | "completed" | "failed";
  state: AgentRunState | null;
  created_at: string;
  completed_at: string | null;
}

export interface SessionResponse {
  id: string;
  user_id: string | null;
  created_at: string;
  runs: AgentRunResponse[];
}

export interface ApprovalResponse {
  id: string;
  agent_run_id: string;
  action_type: string;
  action_details: { message?: string; [key: string]: unknown };
  status: "pending" | "approved" | "rejected";
  created_at: string;
}
