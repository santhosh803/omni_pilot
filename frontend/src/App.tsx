import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import ReactMarkdown from "react-markdown";
// @ts-ignore
import html2pdf from "html2pdf.js";
import {
  Compass,
  Plus,
  RefreshCw,
  Check,
  X,
  Send,
  FileText,
  Download,
  Calendar,
  Search,
  ShieldAlert,
  CheckCircle2,
  Cpu,
  Sparkles,
  ChevronRight,
  TrendingUp,
  Clock,
  ExternalLink,
  Loader2,
  Trash2
} from "lucide-react";
import {
  createSession,
  listSessions,
  getSession,
  triggerRun,
  getPendingApprovals,
  respondApproval,
  deleteSession
} from "./api";
import type { SessionResponse, ApprovalResponse, Message, AgentRunResponse } from "./types";
import "./App.css";

export default function App() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    localStorage.getItem("active_session_id")
  );
  const [activeSession, setActiveSession] = useState<SessionResponse | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [query, setQuery] = useState("");
  const [approvals, setApprovals] = useState<ApprovalResponse[]>([]);
  const [activeTab, setActiveTab] = useState<"briefing" | "observability">("briefing");

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Fetch session list
  const fetchSessionList = async (selectLatestIfNone = false) => {
    setIsLoadingList(true);
    try {
      const list = await listSessions();
      setSessions(list);
      if (selectLatestIfNone && list.length > 0 && !activeSessionId) {
        handleSelectSession(list[0].id);
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setIsLoadingList(false);
    }
  };

  // Fetch active session details
  const fetchSessionDetails = async (id: string, quiet = false) => {
    if (!quiet) setIsLoadingSession(true);
    try {
      const data = await getSession(id);
      setActiveSession(data);
      
      // Determine if a run is currently active/running to set executing state
      const hasRunningJobs = data.runs?.some(
        (r) => r.status === "running" || r.status === "pending"
      );
      setIsExecuting(Boolean(hasRunningJobs));
    } catch (err) {
      console.error("Failed to get session details:", err);
    } finally {
      if (!quiet) setIsLoadingSession(false);
    }
  };

  // Fetch pending HITL approvals
  const fetchApprovals = async () => {
    try {
      const allApprovals = await getPendingApprovals();
      // Filter approvals matching the active session's runs
      if (activeSession && activeSession.runs) {
        const runIds = activeSession.runs.map((r) => r.id);
        const filtered = allApprovals.filter((appr) => runIds.includes(appr.agent_run_id));
        setApprovals(filtered);
      } else {
        setApprovals([]);
      }
    } catch (err) {
      console.error("Failed to fetch approvals:", err);
    }
  };

  // Initial load
  useEffect(() => {
    fetchSessionList(true);
  }, []);

  // Sync session details when active ID changes
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem("active_session_id", activeSessionId);
      fetchSessionDetails(activeSessionId);
    } else {
      localStorage.removeItem("active_session_id");
      setActiveSession(null);
    }
  }, [activeSessionId]);

  // Polling loop for active execution or pending approvals
  useEffect(() => {
    let intervalId: number | undefined;

    // Poll if a run is executing, or if we have active session loaded (to sync new states)
    if (activeSessionId) {
      intervalId = window.setInterval(() => {
        fetchSessionDetails(activeSessionId, true);
        fetchApprovals();
      }, 3000);
    }

    return () => {
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [activeSessionId, activeSession?.runs]);

  // Sync approvals on initial load of active session
  useEffect(() => {
    if (activeSessionId && activeSession) {
      fetchApprovals();
    }
  }, [activeSession, activeSessionId]);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeSession?.runs]);

  // Handle selecting a session
  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setApprovals([]);
  };

  // Create new session
  const handleCreateSession = async () => {
    try {
      const data = await createSession();
      setActiveSessionId(data.id);
      fetchSessionList();
    } catch (err) {
      alert(`Error creating session: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Delete a session
  const handleDeleteSession = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this workspace and all its history?")) {
      return;
    }
    try {
      await deleteSession(id);
      if (activeSessionId === id) {
        const remainingSessions = sessions.filter((s) => String(s.id) !== id);
        if (remainingSessions.length > 0) {
          setActiveSessionId(String(remainingSessions[0].id));
        } else {
          setActiveSessionId(null);
        }
      }
      fetchSessionList();
    } catch (err) {
      alert(`Error deleting session: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Trigger agent run
  const handleExecuteRun = async (queryText?: string) => {
    const textToRun = queryText || query;
    if (!activeSessionId) {
      alert("Please select or create a session first.");
      return;
    }
    if (!textToRun.trim()) {
      alert("Please enter a query.");
      return;
    }

    setIsExecuting(true);
    if (!queryText) setQuery("");

    try {
      await triggerRun(activeSessionId, textToRun);
      await fetchSessionDetails(activeSessionId);
      fetchSessionList();
    } catch (err) {
      alert(`Execution failed: ${err instanceof Error ? err.message : String(err)}`);
      setIsExecuting(false);
    }
  };

  // Respond to HITL Approval
  const handleApprovalResponse = async (approvalId: string, approve: boolean) => {
    try {
      await respondApproval(approvalId, approve);
      setApprovals((prev) => prev.filter((a) => a.id !== approvalId));
      if (activeSessionId) {
        await fetchSessionDetails(activeSessionId);
      }
    } catch (err) {
      alert(`Approval error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Extract all messages from active runs
  const getChatMessages = (): Message[] => {
    if (!activeSession?.runs) return [];
    
    // We want to extract messages from the state of all runs
    const messages: Message[] = [];
    activeSession.runs.forEach((run) => {
      if (run.state?.messages) {
        run.state.messages.forEach((msg) => {
          // Avoid duplicate messages if they appear in sequential runs
          const isDup = messages.some(
            (m) => m.role === msg.role && m.content === msg.content && m.name === msg.name
          );
          if (!isDup) {
            messages.push(msg);
          }
        });
      }
    });

    return messages;
  };

  // Get active research output (if any)
  const getResearchOutput = () => {
    if (!activeSession?.runs) return null;
    
    // Look at runs from newest to oldest for research output
    for (let i = activeSession.runs.length - 1; i >= 0; i--) {
      const run = activeSession.runs[i];
      if (run.state?.research_output) {
        return {
          output: run.state.research_output,
          confidence: run.state.research_confidence || 0,
          sources: run.state.research_sources || []
        };
      }
    }
    return null;
  };

  const researchData = getResearchOutput();
  const chatMessages = getChatMessages();

  // Export PDF of briefing report
  const handleDownloadPDF = () => {
    if (!researchData || !researchData.output) return;

    const element = document.createElement("div");
    element.className = "pdf-export-container";
    element.style.padding = "30px";
    element.style.color = "#1f2937";
    element.style.backgroundColor = "#ffffff";
    element.style.fontFamily = "'Outfit', sans-serif";
    element.style.lineHeight = "1.6";

    // Add PDF Header
    element.innerHTML = `
      <div style="border-bottom: 2px solid #6366f1; padding-bottom: 15px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h1 style="color: #0f172a; font-size: 24px; font-weight: 700; margin: 0;">OmniPilot AI</h1>
          <p style="color: #6b7280; font-size: 12px; margin: 5px 0 0 0;">Market Research & Intelligence Report</p>
        </div>
        <div style="text-align: right;">
          <p style="color: #374151; font-size: 11px; margin: 0;"><b>Date:</b> ${new Date().toLocaleDateString()}</p>
          <p style="color: #374151; font-size: 11px; margin: 3px 0 0 0;"><b>Session ID:</b> #${activeSessionId}</p>
        </div>
      </div>
      <div style="margin-bottom: 20px; font-size: 12px; color: #4b5563;">
        <span><b>Confidence Score:</b> ${(researchData.confidence * 100).toFixed(1)}%</span> | 
        <span><b>Sources Cited:</b> ${researchData.sources.length}</span>
      </div>
      <div id="pdf-markdown-content" style="font-size: 14px; color: #334155;"></div>
    `;

    document.body.appendChild(element);
    
    // Inject rendered markdown text inside pdf container
    const mdContainer = element.querySelector("#pdf-markdown-content");
    if (mdContainer) {
      // Simple rendering workaround for pdf download since marked is not globally imported in vite
      // We'll temporarily copy the HTML inside the rendered preview
      const previewEl = document.querySelector(".briefing-rendered-body");
      if (previewEl) {
        mdContainer.innerHTML = previewEl.innerHTML;
      } else {
        (mdContainer as HTMLElement).innerText = researchData.output;
      }
    }

    const opt = {
      margin: 15,
      filename: `OmniPilot_Research_Briefing_Session_${activeSessionId}.pdf`,
      image: { type: "jpeg" as const, quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, logging: false },
      jsPDF: { unit: "mm" as const, format: "a4" as const, orientation: "portrait" as const }
    };

    html2pdf().set(opt).from(element).save().then(() => {
      document.body.removeChild(element);
    });
  };

  // Get agent specific labels/styling
  const getAgentBadge = (name?: string) => {
    const badgeName = name?.toLowerCase() || "";
    switch (badgeName) {
      case "supervisor":
        return { label: "Supervisor", icon: <Cpu size={12} />, className: "badge-supervisor" };
      case "browser":
        return { label: "Browser Agent", icon: <Search size={12} />, className: "badge-browser" };
      case "calendar":
        return { label: "Calendar Agent", icon: <Calendar size={12} />, className: "badge-calendar" };
      case "research":
        return { label: "Research Agent", icon: <Sparkles size={12} />, className: "badge-research" };
      default:
        return { label: name || "System", icon: <Compass size={12} />, className: "badge-system" };
    }
  };

  // Preset query buttons
  const presets = [
    { text: "Prepare a deep research report on AI agent trends", icon: <Sparkles size={16} /> },
    { text: "Search the web for Qwen 2.5 32B benchmarks", icon: <Search size={16} /> },
    { text: "Schedule a meeting with the client tomorrow", icon: <Calendar size={16} /> }
  ];

  // Calculate run stats
  const getRunStats = (run: AgentRunResponse) => {
    const start = new Date(run.created_at).getTime();
    const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
    const duration = ((end - start) / 1000).toFixed(1);
    
    // Resolve model based on query heuristic / task routing
    let routedModel = "Llama 3.1 8B (Text Processing)";
    if (run.agent_type === "research") {
      routedModel = "Llama 3.3 70B (CrewAI Sub-crew)";
    } else if (run.agent_type === "browser") {
      routedModel = "Qwen 2.5 32B (Web Scraping)";
    } else if (run.agent_type === "supervisor") {
      routedModel = "Llama 3.3 70B (Orchestrator)";
    }

    return { duration, routedModel };
  };

  return (
    <div className="app-container">
      {/* 1. LEFT SIDEBAR — Sessions & Approvals */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <Compass className="logo-icon animate-pulse-slow" size={24} />
            <h2>OmniPilot AI</h2>
          </div>
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>Server Active</span>
          </div>
        </div>

        <button className="btn btn-new" onClick={handleCreateSession}>
          <Plus size={16} />
          <span>New Workspace</span>
        </button>

        <div className="sidebar-section">
          <h3 className="section-title">
            <Clock size={14} />
            <span>Recent Workspaces</span>
            {isLoadingList && <Loader2 size={12} className="animate-spin text-muted" />}
          </h3>
          <div className="session-list">
            {sessions.map((s) => {
              const isActive = String(activeSessionId) === String(s.id);
              return (
                <button
                  key={s.id}
                  className={`session-item ${isActive ? "active" : ""}`}
                  onClick={() => handleSelectSession(s.id)}
                >
                  <div className="session-info">
                    <span className="session-id">Workspace #{s.id}</span>
                    <span className="session-time">
                      {new Date(s.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </span>
                  </div>
                  <div className="session-actions">
                    <span
                      className="btn-delete-session"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(s.id);
                      }}
                      title="Delete Workspace"
                    >
                      <Trash2 size={16} />
                    </span>
                    <ChevronRight size={14} className="chevron" />
                  </div>
                </button>
              );
            })}
            {sessions.length === 0 && !isLoadingList && (
              <div className="empty-state-sidebar">
                <span>No workspaces active. Click New.</span>
              </div>
            )}
          </div>
        </div>

        {/* HITL Approvals Inside Sidebar */}
        <div className="sidebar-section approvals-section">
          <h3 className="section-title text-amber">
            <ShieldAlert size={14} />
            <span>HITL Approvals</span>
            {approvals.length > 0 && <span className="approval-count">{approvals.length}</span>}
          </h3>
          <div className="approvals-list">
            {approvals.map((appr) => (
              <div key={appr.id} className="approval-card animate-slide-in">
                <div className="approval-card-header">
                  <span className="approval-tag">Action Required</span>
                  <span className="approval-type">{appr.action_type}</span>
                </div>
                <p className="approval-msg">
                  {appr.action_details?.message || "Confirm execution of this agent run step."}
                </p>
                <div className="approval-actions">
                  <button
                    className="btn btn-approve"
                    onClick={() => handleApprovalResponse(appr.id, true)}
                  >
                    <Check size={14} /> Approve
                  </button>
                  <button
                    className="btn btn-reject"
                    onClick={() => handleApprovalResponse(appr.id, false)}
                  >
                    <X size={14} /> Reject
                  </button>
                </div>
              </div>
            ))}
            {approvals.length === 0 && (
              <div className="empty-state-approvals">
                <CheckCircle2 size={24} className="text-emerald" />
                <span>All actions approved.</span>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* 2. CENTER PANEL — Chat Feed & Agent Logs */}
      <main className="chat-panel">
        <header className="chat-header">
          <div className="chat-header-info">
            <h3>Interactive Assistant</h3>
            <p className="text-muted">
              {activeSessionId ? `Active Session: #${activeSessionId}` : "Select workspace to begin"}
            </p>
          </div>
          <button
            className="btn btn-icon"
            onClick={() => activeSessionId && fetchSessionDetails(activeSessionId)}
            disabled={!activeSessionId}
            title="Sync Status"
          >
            <RefreshCw size={16} className={isExecuting ? "animate-spin" : ""} />
          </button>
        </header>

        <div className="chat-messages-container">
          {isLoadingSession ? (
            <div className="chat-loading">
              <Loader2 size={36} className="animate-spin text-indigo" />
              <span>Loading workspace logs...</span>
            </div>
          ) : activeSessionId ? (
            chatMessages.length > 0 ? (
              <div className="chat-feed">
                {chatMessages.map((msg, idx) => {
                  const isHuman = msg.role === "human";
                  const agent = getAgentBadge(isHuman ? "User" : msg.name);
                  
                  // Style thinking processes differently
                  const isThought = msg.name === "supervisor" && msg.content.startsWith("[");

                  return (
                    <div
                      key={idx}
                      className={`chat-bubble-wrapper ${isHuman ? "bubble-human" : "bubble-ai"} ${
                        isThought ? "bubble-thought-wrapper" : ""
                      }`}
                    >
                      <div className="bubble-header">
                        {agent.icon}
                        <span className="agent-name">{agent.label}</span>
                        {!isHuman && msg.name && (
                          <span className={`badge-pill ${agent.className}`}>{msg.name}</span>
                        )}
                      </div>
                      <div className={`bubble-body ${isThought ? "thought-process" : ""}`}>
                        {isThought ? (
                          <div className="thought-header">System Routing Logic & Instructions</div>
                        ) : null}
                        <p>{msg.content}</p>
                      </div>
                    </div>
                  );
                })}
                {isExecuting && (
                  <div className="chat-bubble-wrapper bubble-ai">
                    <div className="bubble-header text-indigo">
                      <Loader2 size={12} className="animate-spin" />
                      <span className="agent-name">Agent Network</span>
                      <span className="badge-pill badge-supervisor">thinking</span>
                    </div>
                    <div className="bubble-body thinking-placeholder">
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            ) : (
              <div className="chat-welcome">
                <Sparkles size={48} className="text-indigo animate-pulse-slow" />
                <h2>Welcome to your workspace</h2>
                <p className="text-muted">
                  Ask the assistant to research topics, search the web, or manage your scheduling.
                </p>
                <div className="presets-grid">
                  {presets.map((preset, idx) => (
                    <button
                      key={idx}
                      className="preset-card"
                      onClick={() => handleExecuteRun(preset.text)}
                    >
                      <div className="preset-icon">{preset.icon}</div>
                      <p className="preset-text">{preset.text}</p>
                    </button>
                  ))}
                </div>
              </div>
            )
          ) : (
            <div className="chat-welcome">
              <Compass size={64} className="text-muted" />
              <h2>No workspace selected</h2>
              <p className="text-muted">
                Create a new workspace or select an existing session from the history to inspect and trigger runs.
              </p>
              <button className="btn btn-primary" onClick={handleCreateSession}>
                <Plus size={16} /> Create Workspace
              </button>
            </div>
          )}
        </div>

        {activeSessionId && (
          <form
            className="chat-input-form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              handleExecuteRun();
            }}
          >
            <div className="chat-input-wrapper">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type your request here (e.g. Prepare research report on AI agent trends...)"
                rows={2}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleExecuteRun();
                  }
                }}
              />
              <button
                type="submit"
                className="btn btn-send"
                disabled={isExecuting || !query.trim()}
              >
                {isExecuting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </form>
        )}
      </main>

      {/* 3. RIGHT PANEL — Research Briefing / Artifact Viewer */}
      <section className="artifact-panel">
        <header className="tabs-header">
          <div className="tabs">
            <button
              className={`tab-btn ${activeTab === "briefing" ? "active" : ""}`}
              onClick={() => setActiveTab("briefing")}
            >
              <FileText size={14} />
              <span>Briefing Report</span>
            </button>
            <button
              className={`tab-btn ${activeTab === "observability" ? "active" : ""}`}
              onClick={() => setActiveTab("observability")}
            >
              <Cpu size={14} />
              <span>Observability Logs</span>
            </button>
          </div>
          {activeTab === "briefing" && researchData && (
            <button className="btn btn-download" onClick={handleDownloadPDF} title="Download PDF">
              <Download size={14} /> PDF
            </button>
          )}
        </header>

        <div className="tab-content-container">
          {activeTab === "briefing" ? (
            researchData ? (
              <div className="briefing-container">
                <div className="briefing-meta">
                  <div className="meta-item">
                    <TrendingUp size={14} className="text-emerald" />
                    <span>
                      Confidence: <b>{(researchData.confidence * 100).toFixed(1)}%</b>
                    </span>
                  </div>
                  <div className="meta-item">
                    <ExternalLink size={14} className="text-indigo" />
                    <span>
                      Sources: <b>{researchData.sources.length}</b>
                    </span>
                  </div>
                </div>
                <div className="briefing-rendered-body">
                  <ReactMarkdown>{researchData.output}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div className="empty-state-artifact">
                <FileText size={48} className="text-muted" />
                <h3>No Research Output</h3>
                <p className="text-muted">
                  Trigger a workflow that compiles research briefings. The resulting report will display here dynamically.
                </p>
              </div>
            )
          ) : (
            /* Observability Logs */
            <div className="observability-container">
              <h3>Agent Orchestration Pipeline</h3>
              <p className="text-muted-desc">
                Real-time tracking of agent execution chains, including latencies, and routed models.
              </p>
              
              {activeSession && activeSession.runs && activeSession.runs.length > 0 ? (
                <div className="logs-timeline">
                  {activeSession.runs.map((run) => {
                    const { duration, routedModel } = getRunStats(run);
                    const agentStyle = getAgentBadge(run.agent_type);

                    return (
                      <div key={run.id} className="timeline-item">
                        <div className="timeline-node">
                          {agentStyle.icon}
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-meta">
                            <span className="log-run-id">Run #{run.id}</span>
                            <span className={`log-status status-${run.status}`}>{run.status}</span>
                          </div>
                          <div className="log-details">
                            <div className="log-row">
                              <span className="label">Agent Node:</span>
                              <span className="value capitalize">{run.agent_type}</span>
                            </div>
                            <div className="log-row">
                              <span className="label">AI Model:</span>
                              <span className="value text-indigo">{routedModel}</span>
                            </div>
                            <div className="log-row">
                              <span className="label">Latency:</span>
                              <span className="value"><Clock size={12} style={{ display: 'inline', marginRight: '4px' }} /> {duration}s</span>
                            </div>
                            <div className="log-row">
                              <span className="label">Started At:</span>
                              <span className="value">
                                {new Date(run.created_at).toLocaleTimeString()}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state-artifact">
                  <Cpu size={48} className="text-muted" />
                  <h3>No Execution Logs</h3>
                  <p className="text-muted">
                    Start a new run to observe model routing and token latencies in real time.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
