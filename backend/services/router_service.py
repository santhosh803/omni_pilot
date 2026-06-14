def select_model_for_task(query: str) -> str:
    """AI Router mapping tasks to specific Groq models based on complexity (Phase 3)."""
    query_lower = query.lower()
    
    # Detect query intents
    has_calendar = any(kw in query_lower for kw in ["calendar", "schedule", "event", "appointment", "summar", "classif"])
    has_browser = any(kw in query_lower for kw in ["search", "browse", "page", "url", "extract", "website"])
    has_research = any(kw in query_lower for kw in ["research", "briefing", "report", "prepare"])
    
    # 1. Complex reasoning / Multi-step Orchestration
    if (has_calendar and has_browser) or has_research:
        model = "llama-3.3-70b-versatile"
        reason = "Using Llama 70B for multi-step agent orchestration or deep research briefings."
        
    # 2. Browser reasoning tasks
    elif has_browser:
        model = "qwen-2.5-32b"
        reason = "Using Qwen 32B for web browser searches and DOM operations."
        
    # 3. Simple single-action cheap operations
    else:
        model = "llama-3.1-8b-instant"
        reason = "Using Llama 8B for simple single-action tasks (simple calendar logging, text processing)."
        
    print(f"AI Router Decision: Routed to '{model}' -> Reason: {reason}")
    return model
