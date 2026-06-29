import { useState, useEffect, useCallback } from 'react';
import { Menu, X } from 'lucide-react';
import {
  fetchSessions,
  fetchSession,
  createSession,
  submitRun,
  respondApproval,
  fetchPendingApprovals,
} from './api';
import type { Session, Message, Approval } from './api';
import { SessionSidebar } from './components/SessionSidebar';
import { ChatPanel } from './components/ChatPanel';
import { BriefingViewer } from './components/BriefingViewer';
import './styles.css';

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [researchOutput, setResearchOutput] = useState<string | undefined>(undefined);
  const [researchSources, setResearchSources] = useState<string[] | undefined>(undefined);
  const [researchConfidence, setResearchConfidence] = useState<number | undefined>(undefined);
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

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

  // Submit run / query
  const handleSendMessage = async (query: string) => {
    if (activeSessionId === null) return;
    try {
      setIsLoading(true);
      // Optimistically append user message to feed
      setMessages(prev => [...prev, { role: 'human', content: query }]);
      await submitRun(activeSessionId, query);
      await loadSessionDetails();
    } catch (err) {
      alert(`Execution Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsLoading(false);
    }
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
