import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Globe, Calendar, BookOpen, Send, ChevronDown, ShieldAlert, Loader } from 'lucide-react';
import type { Message, Approval } from '../api';

interface ChatPanelProps {
  messages: Message[];
  pendingApprovals: Approval[];
  onRespondApproval: (id: number, approve: boolean) => void;
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  activeSessionId: number | null;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  pendingApprovals,
  onRespondApproval,
  onSendMessage,
  isLoading,
  activeSessionId,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingApprovals, isLoading]);

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

  // Helper to render message headers & badges
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

    const name = msg.name || 'Assistant';
    const lowerName = name.toLowerCase();

    let Icon = Bot;
    let badgeClass = 'supervisor';

    if (lowerName.includes('browser')) {
      Icon = Globe;
      badgeClass = 'browser';
    } else if (lowerName.includes('calendar')) {
      Icon = Calendar;
      badgeClass = 'calendar';
    } else if (lowerName.includes('research')) {
      Icon = BookOpen;
      badgeClass = 'research';
    }

    return (
      <div className="message-header-meta assistant-meta">
        <Icon size={14} />
        <span>{name}</span>
        <span className={`agent-badge ${badgeClass}`}>{name}</span>
      </div>
    );
  };

  return (
    <div className="chat-panel-container">
      <div className="chat-header">
        <Bot size={18} style={{ color: 'var(--accent-violet)' }} />
        <span>Execution Activity Feed</span>
      </div>

      <div className="chat-messages-scroll">
        {activeSessionId === null ? (
          <div className="empty-state">
            <Bot size={48} />
            <p>Create or load a session to view the activity feed.</p>
          </div>
        ) : messages.length === 0 ? (
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

        {isLoading && (
          <div className="message-bubble assistant" style={{ alignSelf: 'flex-start' }}>
            <div className="message-header-meta assistant-meta">
              <Loader size={14} className="animate-spin" />
              <span>Supervisor</span>
            </div>
            <div style={{ marginTop: '0.25rem', color: 'var(--text-muted)' }}>
              Agent is executing task...
            </div>
          </div>
        )}

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
      </div>
    </div>
  );
};
