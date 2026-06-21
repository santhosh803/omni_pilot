from crewai import Task

def create_plan_task(agent) -> Task:
    return Task(
        description="Analyze the user query: '{query}' and break it down into 3-5 targeted sub-questions for research. Focus on covering all facets of the query comprehensively.",
        expected_output="A numbered or bulleted list of 3-5 targeted sub-questions.",
        agent=agent
    )

def create_crawl_task(agent, context_tasks) -> Task:
    return Task(
        description="For each sub-question identified in the research plan, perform web searches and/or fetch relevant page contents using your tools. Extract raw facts and content. Document findings under each sub-question, listing the exact source URLs.",
        expected_output="Raw research findings grouped by sub-question, including source URLs.",
        agent=agent,
        context=context_tasks
    )

def create_analyse_task(agent, context_tasks) -> Task:
    return Task(
        description="""Review the raw web findings from the crawler. 
Cross-reference findings across sources, identify any gaps, and score the relevance/credibility of information. 
Output your analysis in a structured format containing findings, source citations, and confidence scores (between 0.0 and 1.0).""",
        expected_output="Structured analysis with findings, citations, and confidence scores.",
        agent=agent,
        context=context_tasks
    )

def create_write_task(agent, context_tasks) -> Task:
    return Task(
        description="""Synthesize the analyst output into a professional, executive-level research briefing. 
The briefing must be structured in clean markdown. 
Ensure it has inline citations matching the sources and concludes with a bibliography/sources list. 
It must be thorough, clear, and action-oriented.""",
        expected_output="A clean, structured markdown briefing with inline citations and a sources list.",
        agent=agent,
        context=context_tasks
    )
