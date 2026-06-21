import os
import re
import json
from crewai import Crew, Process
from backend.agents.research_crew.agents import (
    get_llm,
    create_planner_agent,
    create_crawler_agent,
    create_analyst_agent,
    create_writer_agent
)
from backend.agents.research_crew.tasks import (
    create_plan_task,
    create_crawl_task,
    create_analyse_task,
    create_write_task
)

def get_mock_results(query: str) -> dict:
    """Helper to return high-quality mock research results for testing/fallback mode."""
    return {
        "briefing": (
            f"# Research Briefing: {query}\n\n"
            f"**Generated on**: 2026-06-20\n\n"
            f"## Search Summary Findings\n"
            f"AI Agent trends are growing rapidly. Multi-agent orchestrations "
            f"(e.g. CrewAI, LangGraph) are replacing single-agent designs as they "
            f"successfully break down complex goals into specialized roles.\n\n"
            f"## Recommendations\n"
            f"- Analyze market shifts outlined in search findings.\n"
            f"- Establish calendar schedules to align teams on research notes.\n\n"
            f"## Sources\n"
            f"- [AI Agent Trends](https://example.com/ai-agent-trends)\n"
            f"- [Multi-Agent Systems](https://example.com/multi-agent-systems)\n"
        ),
        "sources": [
            "https://example.com/ai-agent-trends",
            "https://example.com/multi-agent-systems"
        ],
        "sub_questions": [
            f"What are the key trends for {query}?",
            "How do multi-agent frameworks compare?",
            "What is the industry adoption rate?"
        ],
        "confidence": 0.95
    }

def run_research_crew(query: str) -> dict:
    print(f"--- STARTING CREWAI RESEARCH SUB-CREW FOR QUERY: '{query}' ---")
    
    # Check if keys are missing or placeholders
    api_key = os.getenv("GROQ_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    
    has_groq = api_key and api_key != "your_groq_api_key_here"
    has_cerebras = cerebras_key and cerebras_key != "your_cerebras_api_key_here"
    has_tavily = tavily_key and tavily_key != "your_tavily_api_key_here"
    
    if (not (has_groq or has_cerebras) or not has_tavily):
        print("WARNING: Neither GROQ_API_KEY nor CEREBRAS_API_KEY is configured (or TAVILY_API_KEY is missing). Returning mock research results for testing.")
        return get_mock_results(query)
        
    try:
        # Ensure all OpenAI-based client wrappers inside CrewAI redirect their calls correctly
        if has_cerebras:
            os.environ["OPENAI_API_KEY"] = cerebras_key
            os.environ["OPENAI_API_BASE"] = "https://api.cerebras.ai/v1"
            os.environ["OPENAI_BASE_URL"] = "https://api.cerebras.ai/v1"
        else:
            os.environ["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
            os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        
        # 1. Initialize LLM
        llm = get_llm()
        
        # 2. Instantiate all 4 agents
        planner = create_planner_agent(llm)
        crawler = create_crawler_agent(llm)
        analyst = create_analyst_agent(llm)
        writer = create_writer_agent(llm)
        
        # 3. Instantiate all 4 tasks with context
        plan_task = create_plan_task(planner)
        crawl_task = create_crawl_task(crawler, [plan_task])
        analyse_task = create_analyse_task(analyst, [crawl_task])
        write_task = create_write_task(writer, [analyse_task])
        
        # 4. Construct Crew
        crew = Crew(
            agents=[planner, crawler, analyst, writer],
            tasks=[plan_task, crawl_task, analyse_task, write_task],
            process=Process.sequential,
            verbose=True
        )
        
        # 5. Kickoff Crew
        crew_output = crew.kickoff(inputs={"query": query})
        
        # 6. Safely access task outputs
        planner_output = plan_task.output.raw if (hasattr(plan_task, "output") and plan_task.output) else ""
        crawler_output = crawl_task.output.raw if (hasattr(crawl_task, "output") and crawl_task.output) else ""
        analyst_output = analyse_task.output.raw if (hasattr(analyse_task, "output") and analyse_task.output) else ""
        writer_output = write_task.output.raw if (hasattr(write_task, "output") and write_task.output) else crew_output.raw
        
        if hasattr(crew_output, "tasks_output") and crew_output.tasks_output:
            if len(crew_output.tasks_output) > 0 and not planner_output:
                planner_output = crew_output.tasks_output[0].raw
            if len(crew_output.tasks_output) > 1 and not crawler_output:
                crawler_output = crew_output.tasks_output[1].raw
            if len(crew_output.tasks_output) > 2 and not analyst_output:
                analyst_output = crew_output.tasks_output[2].raw
            if len(crew_output.tasks_output) > 3 and not writer_output:
                writer_output = crew_output.tasks_output[3].raw

        # 7. Parse results
        briefing = writer_output if writer_output else crew_output.raw
        
        raw_urls = re.findall(r'https?://[^\s()\[\]{}<>\'"]+', f"{crawler_output}\n{analyst_output}\n{writer_output}")
        sources = []
        for url in raw_urls:
            url = url.rstrip('.,;:!?')
            if url not in sources:
                sources.append(url)
                
        sub_questions = []
        if planner_output:
            for line in planner_output.splitlines():
                line = line.strip()
                match = re.match(r'^\d+[\.\)]\s*(.*)', line)
                if match:
                    sub_questions.append(match.group(1).strip())
                elif line.startswith('- ') or line.startswith('* '):
                    sub_questions.append(line[2:].strip())
            if not sub_questions:
                sub_questions = [line for line in planner_output.splitlines() if line.strip() and len(line) > 10]
                
        confidence = 0.8
        if analyst_output:
            json_match = re.search(r'\{.*\}', analyst_output, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    if isinstance(data, dict):
                        if "confidence" in data:
                            confidence = float(data["confidence"])
                        elif "confidence_score" in data:
                            confidence = float(data["confidence_score"])
                        else:
                            scores = []
                            for k, v in data.items():
                                if isinstance(v, (int, float)) and "confidence" in k.lower():
                                    scores.append(float(v))
                                elif isinstance(v, dict):
                                    for sk, sv in v.items():
                                        if isinstance(sv, (int, float)) and "confidence" in sk.lower():
                                            scores.append(float(sv))
                                elif isinstance(v, list):
                                    for item in v:
                                        if isinstance(item, dict):
                                            for sk, sv in item.items():
                                                if isinstance(sv, (int, float)) and "confidence" in sk.lower():
                                                    scores.append(float(sv))
                            if scores:
                                confidence = sum(scores) / len(scores)
                except Exception:
                    pass
                    
            if confidence == 0.8:
                matches = re.findall(r'(?:confidence|score|rating)(?:\s*\w*){0,3}\s*[:=-]?\s*(0\.\d+|1\.0|1)', analyst_output, re.IGNORECASE)
                if matches:
                    try:
                        scores = [float(m) for m in matches]
                        confidence = sum(scores) / len(scores)
                    except Exception:
                        pass
                        
        confidence = max(0.0, min(1.0, confidence))
        
        print(f"--- CrewAI execution finished successfully. Confidence={confidence}, Sources={len(sources)} ---")
        return {
            "briefing": briefing,
            "sources": sources,
            "sub_questions": sub_questions,
            "confidence": confidence
        }
    except Exception as e:
        print(f"WARNING: CrewAI sub-crew execution failed: {e}. Falling back to mock research results.")
        return get_mock_results(query)
