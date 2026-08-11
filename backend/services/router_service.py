def select_model_for_task(query: str) -> str:
    """AI Router mapping tasks to specific Gemini models based on complexity.

    Tier mapping:
      - complex / multi-step / research → gemini-2.5-pro
      - browser / DOM operations        → gemini-2.5-flash
      - simple / cheap single-action    → gemini-2.5-flash-lite
    """
    query_lower = query.lower()

    # Detect query intents
    has_calendar = any(
        kw in query_lower
        for kw in ["calendar", "schedule", "event", "appointment", "summar", "classif"]
    )
    has_browser = any(
        kw in query_lower for kw in ["search", "browse", "page", "url", "extract", "website"]
    )
    has_research = any(kw in query_lower for kw in ["research", "briefing", "report", "prepare"])

    # 1. Complex reasoning / Multi-step Orchestration
    if (has_calendar and has_browser) or has_research:
        model = "gemini-2.5-pro"
        reason = (
            "Using Gemini 2.5 Pro for multi-step agent orchestration or deep research briefings."
        )

    # 2. Browser reasoning tasks
    elif has_browser:
        model = "gemini-2.5-flash"
        reason = "Using Gemini 2.5 Flash for web browser searches and DOM operations."

    # 3. Simple single-action cheap operations
    else:
        model = "gemini-2.5-flash-lite"
        reason = (
            "Using Gemini 2.5 Flash-Lite for simple single-action tasks "
            "(simple calendar logging, text processing)."
        )

    print(f"AI Router Decision: Routed to '{model}' -> Reason: {reason}")
    return model
