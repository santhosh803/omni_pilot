import { useState, useEffect, useCallback } from 'react';
import { Menu, X } from 'lucide-react';
import {
  fetchSessions,
  fetchSession,
  createSession,
  deleteSession,
  submitRunStream,
  respondApproval,
  fetchPendingApprovals,
} from './api';
import type { Session, Message, Approval, StreamEvent } from './api';
import { SessionSidebar } from './components/SessionSidebar';
import { ChatPanel } from './components/ChatPanel';
import { BriefingViewer } from './components/BriefingViewer';
import { useTheme } from './hooks/useTheme';
import { ThemeToggle } from './components/ThemeToggle';
import './styles.css';

function App() {
  const { theme, toggleTheme, buttonRef: themeButtonRef } = useTheme();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [researchOutput, setResearchOutput] = useState<string | undefined>(undefined);
  const [researchSources, setResearchSources] = useState<string[] | undefined>(undefined);
  const [researchConfidence, setResearchConfidence] = useState<number | undefined>(undefined);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  // Live streaming state
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string>('');

  // Load session list on mount
  const loadSessions = useCallback(async (selectDefault = false) => {
    try {
      const data = await fetchSessions();
      setSessions(data);
      
      if (selectDefault && data.length > 0) {
        // Look in localStorage first
        const savedId = localStorage.getItem('active_session_id');
        if (savedId) {
          const idNum = parseInt(savedId, 10);
          if (data.some(s => s.id === idNum)) {
            setActiveSessionId(idNum);
            return;
          }
        }
        // Fallback to latest session
        setActiveSessionId(data[0].id);
      }
    } catch (err) {
      console.error('Error loading sessions:', err);
    }
  }, []);

  useEffect(() => {
    loadSessions(true);
  }, [loadSessions]);

  // Load details for the active session
  const loadSessionDetails = useCallback(async () => {
    if (activeSessionId === null) return;
    try {
      const sessionData = await fetchSession(activeSessionId);
      
      // Update this session in the list so list displays correct runs
      setSessions(prev => prev.map(s => s.id === activeSessionId ? sessionData : s));

      const runs = sessionData.runs || [];
      if (runs.length > 0) {
        const latestRun = runs[runs.length - 1];
        const state = latestRun.state || {};
        
        // Update messages
        setMessages(state.messages || []);
        
        // Update briefing
        setResearchOutput(state.research_output);
        setResearchSources(state.research_sources);
        setResearchConfidence(state.research_confidence);

        // Update loading status based on run status
        setIsLoading(latestRun.status === 'running');
      } else {
        setMessages([]);
        setResearchOutput(undefined);
        setResearchSources(undefined);
        setResearchConfidence(undefined);
        setIsLoading(false);
      }
    } catch (err) {
      console.error(`Error loading session #${activeSessionId}:`, err);
    }
  }, [activeSessionId]);

  // Load pending approvals filtered for active session
  const loadApprovals = useCallback(async () => {
    if (activeSessionId === null) return;
    try {
      const approvals = await fetchPendingApprovals();
      const activeSession = sessions.find(s => s.id === activeSessionId);
      const runIds = (activeSession?.runs || []).map(r => r.id);
      
      // Only include approvals belonging to active session runs
      const filtered = approvals.filter(appr => runIds.includes(appr.agent_run_id));
      setPendingApprovals(filtered);
    } catch (err) {
      console.error('Error loading approvals:', err);
    }
  }, [activeSessionId, sessions]);

  // Handle active session changing
  useEffect(() => {
    if (activeSessionId !== null) {
      localStorage.setItem('active_session_id', String(activeSessionId));
      loadSessionDetails();
      loadApprovals();
    } else {
      localStorage.removeItem('active_session_id');
      setMessages([]);
      setResearchOutput(undefined);
      setResearchSources(undefined);
      setResearchConfidence(undefined);
      setPendingApprovals([]);
      setIsLoading(false);
    }
  }, [activeSessionId, loadSessionDetails, loadApprovals]);

  // Set up polling (every 3 seconds)
  useEffect(() => {
    if (activeSessionId === null) return;

    const interval = setInterval(() => {
      loadSessionDetails();
      loadApprovals();
    }, 3000);

    return () => clearInterval(interval);
  }, [activeSessionId, loadSessionDetails, loadApprovals]);

  // Create new session
  const handleCreateSession = async () => {
    try {
      setIsLoading(true);
      const newSess = await createSession();
      // Add to list and select
      setSessions(prev => [newSess, ...prev]);
      setActiveSessionId(newSess.id);
      setIsSidebarOpen(false);
    } catch (err) {
      alert(`Failed to create session: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Select session
  const handleSelectSession = (id: number) => {
    setActiveSessionId(id);
    setIsSidebarOpen(false);
  };

  // Delete session
  const handleDeleteSession = async (id: number) => {
    try {
      await deleteSession(id);
      // Remove from list
      setSessions(prev => prev.filter(s => s.id !== id));
      // If deleting the active session, clear it
      if (id === activeSessionId) {
        setActiveSessionId(null);
      }
    } catch (err) {
      alert(`Failed to delete session: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Submit run / query — uses SSE streaming for live progress
  const handleSendMessage = async (query: string) => {
    if (activeSessionId === null) return;

    // Optimistically append user message and set loading
    setMessages(prev => [...prev, { role: 'human', content: query }]);
    setIsLoading(true);
    setActiveNode(null);
    setStreamStatus('Connecting...');

    const handleEvent = (event: StreamEvent) => {
      const p = event.payload;
      switch (event.type) {
        case 'node_start':
          setActiveNode(p.node as string);
          setStreamStatus(`${p.label as string} is running…`);
          break;

        case 'node_end':
          setStreamStatus(`${p.label as string} completed`);
          break;

        case 'routing': {
          const dest = p.next_label as string;
          setStreamStatus(`Routing → ${dest}`);
          break;
        }

        case 'message': {
          const msg = p as unknown as Message;
          // Avoid duplicating the optimistic human message
          if (msg.role !== 'human') {
            setMessages(prev => [...prev, msg]);
          }
          break;
        }

        case 'interrupt': {
          setStreamStatus('Waiting for your approval…');
          // Reload approvals so the approval card appears immediately
          loadApprovals();
          break;
        }

        case 'complete':
          setStreamStatus('Done');
          break;

        case 'error':
          setStreamStatus(`Error: ${p.error as string}`);
          break;
      }
    };

    await submitRunStream(activeSessionId, query, {
      onEvent: handleEvent,
      onDone: () => {
        setIsLoading(false);
        setActiveNode(null);
        setStreamStatus('');
        // Sync final state from DB (research output, sources, etc.)
        loadSessionDetails();
      },
      onError: (err) => {
        setIsLoading(false);
        setActiveNode(null);
        setStreamStatus('');
        alert(`Execution Error: ${err.message}`);
      },
    });
  };

  // Respond to approval gate
  const handleRespondApproval = async (id: number, approve: boolean) => {
    try {
      setIsLoading(true);
      await respondApproval(id, approve);
      // Instantly load approvals to remove the card
      await loadApprovals();
      await loadSessionDetails();
    } catch (err) {
      alert(`Approval Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Compute Server Status
  const getSystemStatus = (): 'online' | 'busy' | 'error' => {
    if (isLoading) return 'busy';
    
    if (activeSessionId !== null) {
      const activeSession = sessions.find(s => s.id === activeSessionId);
      const runs = activeSession?.runs || [];
      if (runs.length > 0) {
        const latestRun = runs[runs.length - 1];
        if (latestRun.status === 'running') return 'busy';
        if (latestRun.status === 'failed') return 'error';
      }
    }
    
    return 'online';
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            className="mobile-hamburger"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="logo-section">
            <img src="/favicon.svg" alt="OmniPilot Logo" width={20} height={20} />
            <span>OmniPilot AI</span>
            <ThemeToggle theme={theme} onToggle={toggleTheme} buttonRef={themeButtonRef} />
          </div>
        </div>
        <div className="header-actions">
          <div className="status-pill">
            <span className={`status-dot ${getSystemStatus()}`} />
            <span style={{ fontSize: '0.75rem', textTransform: 'capitalize' }}>
              System {getSystemStatus()}
            </span>
          </div>
        </div>
      </header>

      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
        onDeleteSession={handleDeleteSession}
        systemStatus={getSystemStatus()}
        isOpen={isSidebarOpen}
      />

      <ChatPanel
        messages={messages}
        pendingApprovals={pendingApprovals}
        onRespondApproval={handleRespondApproval}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        activeSessionId={activeSessionId}
        activeNode={activeNode}
        streamStatus={streamStatus}
      />

      <BriefingViewer
        researchOutput={researchOutput}
        researchSources={researchSources}
        researchConfidence={researchConfidence}
        activeSessionId={activeSessionId}
      />
    </div>
  );
}

export default App;
