"""Agent service — thin compatibility wrapper.

The graph execution logic has been unified into stream_service.py (Item 6).
This module re-exports the shared functions so existing imports continue to work:

    from backend.services.agent_service import execute_or_resume_graph
    from backend.services.agent_service import serialize_messages
"""

from backend.services.stream_service import execute_or_resume_graph, serialize_messages

__all__ = ["execute_or_resume_graph", "serialize_messages"]
