import React from 'react';
import { PlusCircle, Database, Server } from 'lucide-react';
import type { Session } from '../api';

interface SessionSidebarProps {
  sessions: Session[];
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onCreateSession: () => void;
  systemStatus: 'online' | 'busy' | 'error';
  isOpen: boolean;
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  systemStatus,
  isOpen,
}) => {
  return (
    <aside className={`sidebar-panel ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <button className="new-session-btn" onClick={onCreateSession}>
          <PlusCircle size={16} />
          <span>New Session</span>
        </button>
      </div>

      <div className="session-list-container">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <Database size={24} />
            <p style={{ fontSize: '0.85rem' }}>No recent sessions found.</p>
          </div>
        ) : (
          sessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const dateStr = new Date(session.created_at).toLocaleString(undefined, {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });
            return (
              <div
                key={session.id}
                className={`session-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="session-title">
                  <span>Session #{session.id}</span>
                  {isActive && (
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--accent-violet)',
                        boxShadow: '0 0 6px var(--accent-violet)',
                      }}
                    />
                  )}
                </div>
                <div className="session-meta">{dateStr}</div>
              </div>
            );
          })
        )}
      </div>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Server size={14} />
          <span>Agent Server</span>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${systemStatus}`} />
          <span style={{ textTransform: 'capitalize' }}>{systemStatus}</span>
        </div>
      </div>
    </aside>
  );
};
