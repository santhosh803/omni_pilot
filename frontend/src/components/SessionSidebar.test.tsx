import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SessionSidebar } from './SessionSidebar'

const baseProps = {
  onSelectSession: () => {},
  onCreateSession: () => {},
  systemStatus: 'online' as const,
  isOpen: false,
}

describe('SessionSidebar', () => {
  it('renders the New Session button', () => {
    render(
      <SessionSidebar
        sessions={[]}
        activeSessionId={null}
        {...baseProps}
      />,
    )
    expect(screen.getByText('New Session')).toBeInTheDocument()
  })

  it('shows the empty state when there are no sessions', () => {
    render(
      <SessionSidebar
        sessions={[]}
        activeSessionId={null}
        {...baseProps}
      />,
    )
    expect(screen.getByText('No recent sessions found.')).toBeInTheDocument()
  })

  it('renders session items when sessions are provided', () => {
    const sessions = [
      { id: 1, user_id: null, created_at: '2026-06-29T12:00:00Z', runs: [] },
      { id: 2, user_id: null, created_at: '2026-06-29T13:00:00Z', runs: [] },
    ]
    render(
      <SessionSidebar
        sessions={sessions}
        activeSessionId={1}
        {...baseProps}
      />,
    )
    expect(screen.getByText('Session #1')).toBeInTheDocument()
    expect(screen.getByText('Session #2')).toBeInTheDocument()
  })
})
