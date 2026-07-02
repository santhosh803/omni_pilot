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

export async function deleteSession(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/api/sessions/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete session: ${response.statusText}`);
  }
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

// ---------------------------------------------------------------------------
// SSE Streaming Types
// ---------------------------------------------------------------------------

export type StreamEventType =
  | 'node_start'
  | 'node_end'
  | 'message'
  | 'routing'
  | 'interrupt'
  | 'complete'
  | 'error';

export interface StreamEvent {
  type: StreamEventType;
  payload: Record<string, unknown>;
}

export interface StreamCallbacks {
  onEvent: (event: StreamEvent) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

/**
 * Submit a new agent run using the SSE streaming endpoint.
 * Reads the response body as a ReadableStream, parses SSE lines, and
 * calls the appropriate callback for each event.
 *
 * Uses `fetch` + `ReadableStream` (not `EventSource`) because EventSource
 * only supports GET requests, but our endpoint requires POST with a body.
 */
export async function submitRunStream(
  sessionId: number,
  query: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/sessions/${sessionId}/runs/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    return;
  }

  if (!response.ok || !response.body) {
    callbacks.onError(new Error(`Stream request failed: ${response.statusText}`));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double newlines (\n\n).
      const parts = buffer.split('\n\n');
      // The last part may be an incomplete chunk — keep it in the buffer.
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        const lines = part.split('\n');
        let eventType = '';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice('event: '.length).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice('data: '.length).trim();
          }
        }

        if (eventType && dataStr) {
          try {
            const payload = JSON.parse(dataStr) as Record<string, unknown>;
            callbacks.onEvent({ type: eventType as StreamEventType, payload });
          } catch {
            // Malformed JSON — skip this event
          }
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    return;
  } finally {
    reader.releaseLock();
  }

  callbacks.onDone();
}
