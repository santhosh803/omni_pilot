export interface Message {
  role: 'human' | 'ai' | 'system' | string;
  content: string;
  name?: string;
}

export interface AgentRun {
  id: number;
  session_id: number;
  agent_type: string;
  status: 'running' | 'completed' | 'failed' | 'interrupted' | string;
  state?: {
    messages?: Message[];
    research_output?: string;
    research_sources?: string[];
    research_confidence?: number;
    error?: string;
    [key: string]: any;
  };
  created_at: string;
  completed_at?: string;
}

export interface Session {
  id: number;
  user_id?: number | null;
  created_at: string;
  runs: AgentRun[];
}

export interface Approval {
  id: number;
  agent_run_id: number;
  action_type: string;
  action_details: {
    message?: string;
    [key: string]: any;
  };
  status: 'pending' | 'approved' | 'rejected' | string;
  created_at: string;
}

const API_BASE = ''; // Use relative paths for proxy support in Vite

export async function fetchSessions(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/api/sessions/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchSession(id: number): Promise<Session> {
  const response = await fetch(`${API_BASE}/api/sessions/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch session details: ${response.statusText}`);
  }
  return response.json();
}

export async function createSession(): Promise<Session> {
  const response = await fetch(`${API_BASE}/api/sessions/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: null }),
  });
  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.statusText}`);
  }
  return response.json();
}

export async function submitRun(id: number, query: string): Promise<AgentRun> {
  const response = await fetch(`${API_BASE}/api/sessions/${id}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(`Failed to submit agent run: ${response.statusText}`);
  }
  return response.json();
}

export async function respondApproval(id: number, approve: boolean): Promise<Approval> {
  const response = await fetch(`${API_BASE}/api/approvals/${id}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approve }),
  });
  if (!response.ok) {
    throw new Error(`Failed to respond to approval request: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchPendingApprovals(): Promise<Approval[]> {
  const response = await fetch(`${API_BASE}/api/approvals/pending`);
  if (!response.ok) {
    throw new Error(`Failed to fetch pending approvals: ${response.statusText}`);
  }
  return response.json();
}
