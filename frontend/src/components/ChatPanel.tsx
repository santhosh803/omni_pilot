import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  User,
  Globe,
  Calendar,
  BookOpen,
  Send,
  ChevronDown,
  ShieldAlert,
  Loader,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';
import type { Message, Approval } from '../api';

interface ChatPanelProps {
  messages: Message[];
  pendingApprovals: Approval[];
  onRespondApproval: (id: number, approve: boolean) => void;
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  activeSessionId: number | null;
  /** The internal LangGraph node name currently executing, e.g. "browser" */
  activeNode?: string | null;
  /** A human-readable streaming status string, e.g. "Browser Agent is running…" */
  streamStatus?: string;
}

// Map node names to display config
const NODE_CONFIG: Record<string, { label: string; icon: React.ElementType; color: string; badgeClass: string }> = {
  supervisor:    { label: 'Supervisor',      icon: Bot,      color: 'var(--accent-violet)', badgeClass: 'supervisor' },
  browser:       { label: 'Browser Agent',   icon: Globe,    color: 'var(--success)',        badgeClass: 'browser'    },
  calendar:      { label: 'Calendar Agent',  icon: Calendar, color: 'var(--warning)',         badgeClass: 'calendar'   },
  calendar_read: { label: 'Calendar Agent',  icon: Calendar, color: 'var(--warning)',         badgeClass: 'calendar'   },
  research:      { label: 'Research Agent',  icon: BookOpen, color: 'var(--accent-indigo)',   badgeClass: 'research'   },
};

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  pendingApprovals,
  onRespondApproval,
  onSendMessage,
  isLoading,
  activeSessionId,
  activeNode,
  streamStatus,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingApprovals, isLoading, streamStatus]);

  // Adjust textarea height automatically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [inputValue]);

  const handleSend = () => {
    if (!inputValue.trim() || isLoading || activeSessionId === null) return;
    onSendMessage(inputValue.trim());
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Render the agent badge + icon in the message header
  const renderMessageHeader = (msg: Message) => {
    const isHuman = msg.role === 'human';
    if (isHuman) {
      return (
        <div className="message-header-meta user-meta">
          <User size={14} />
          <span>User</span>
        </div>
      );
    }

    const name = msg.name || 'assistant';
    const lowerName = name.toLowerCase();
    let nodeKey = 'supervisor';
    if (lowerName.includes('browser'))  nodeKey = 'browser';
    else if (lowerName.includes('calendar')) nodeKey = 'calendar';
    else if (lowerName.includes('research')) nodeKey = 'research';

    const cfg = NODE_CONFIG[nodeKey] ?? NODE_CONFIG.supervisor;
    const Icon = cfg.icon;

    return (
      <div className="message-header-meta assistant-meta">
        <Icon size={14} />
        <span>{cfg.label}</span>
        <span className={`agent-badge ${cfg.badgeClass}`}>{cfg.label}</span>
      </div>
    );
  };

  // Render a live "node progress" strip while a node is executing
  const renderNodeProgress = () => {
    if (!isLoading || !activeNode) return null;
    const cfg = NODE_CONFIG[activeNode] ?? NODE_CONFIG.supervisor;
    const Icon = cfg.icon;
    return (
      <div className="node-progress-strip">
        <span className="node-progress-pulse" style={{ background: cfg.color }} />
        <Icon size={13} style={{ color: cfg.color, flexShrink: 0 }} />
        <span className="node-progress-label" style={{ color: cfg.color }}>
          {streamStatus || `${cfg.label} is running…`}
        </span>
      </div>
    );
  };

  // Render the generic loading bubble when loading but no node yet identified
  const renderLoadingBubble = () => {
    if (!isLoading) return null;

    // If we already have an active node, the progress strip (above) is shown instead
    if (activeNode) return null;

    return (
      <div className="message-bubble assistant" style={{ alignSelf: 'flex-start' }}>
        <div className="message-header-meta assistant-meta">
          <Loader size={14} className="animate-spin" />
          <span>Supervisor</span>
        </div>
        <div style={{ marginTop: '0.25rem', color: 'var(--text-muted)' }}>
          {streamStatus || 'Connecting…'}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-panel-container">
      <div className="chat-header">
        <Bot size={18} style={{ color: 'var(--accent-violet)' }} />
        <span>Execution Activity Feed</span>
        {isLoading && (
          <span className="stream-live-badge">
            <span className="stream-live-dot" />
            LIVE
          </span>
        )}
      </div>

      <div className="chat-messages-scroll">
        {activeSessionId === null ? (
          <div className="empty-state">
            <Bot size={48} />
            <p>Create or load a session to view the activity feed.</p>
          </div>
        ) : messages.length === 0 && !isLoading ? (
          <div className="empty-state">
            <Bot size={48} />
            <p>No activity yet. Send a query to start the agent.</p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isHuman = msg.role === 'human';
            const isSupervisor = msg.name?.toLowerCase() === 'supervisor';

            return (
              <div
                key={index}
                className={`message-bubble ${isHuman ? 'user' : 'assistant'}`}
              >
                {renderMessageHeader(msg)}

                {isSupervisor ? (
                  <details className="routing-logs-container" open>
                    <summary className="routing-logs-toggle">
                      <ChevronDown size={14} />
                      <span>Supervisor Routing Details</span>
                    </summary>
                    <div className="routing-logs-content">{msg.content}</div>
                  </details>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap', marginTop: '0.25rem' }}>
                    {msg.content}
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* Live node progress strip — shown while a named node is executing */}
        {renderNodeProgress()}

        {/* Generic loading bubble — shown during connection / before first node */}
        {renderLoadingBubble()}

        {/* Pending Approvals */}
        {pendingApprovals.map((approval) => (
          <div key={approval.id} className="approval-card">
            <div className="approval-title">
              <ShieldAlert size={16} />
              <span>HITL Interrupt: {approval.action_type}</span>
            </div>
            <div className="approval-message">
              {approval.action_details.message || 'Confirm execution of this agent node.'}
            </div>
            <div className="approval-actions">
              <button
                className="approval-btn approve"
                onClick={() => onRespondApproval(approval.id, true)}
                disabled={isLoading}
              >
                <CheckCircle2 size={14} />
                Approve
              </button>
              <button
                className="approval-btn reject"
                onClick={() => onRespondApproval(approval.id, false)}
                disabled={isLoading}
              >
                Reject
              </button>
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="input-container-box">
          <textarea
            ref={textareaRef}
            rows={1}
            className="chat-textarea"
            placeholder={
              activeSessionId === null
                ? 'Select a session first'
                : 'Type what you want the assistant to do...'
            }
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || activeSessionId === null}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading || activeSessionId === null}
          >
            {isLoading ? (
              <Loader size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>

        {/* Live status bar — only visible while streaming */}
        {isLoading && streamStatus && (
          <div className="stream-status-bar">
            <ArrowRight size={12} className="stream-status-arrow" />
            <span>{streamStatus}</span>
          </div>
        )}
      </div>
    </div>
  );
};
