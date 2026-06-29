import os

from crewai import Agent
from langchain_openai import ChatOpenAI

from backend.agents.research_crew.tools import fetch_page_content, tavily_search


def get_llm():
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    if cerebras_key and cerebras_key != "your_cerebras_api_key_here":
        return ChatOpenAI(
            model="gpt-oss-120b",
            temperature=0.1,
            openai_api_key=cerebras_key,
            openai_api_base="https://api.cerebras.ai/v1",
        )
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is not configured in the .env file.")
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        openai_api_key=api_key,
        openai_api_base="https://api.groq.com/openai/v1",
    )


def create_planner_agent(llm) -> Agent:
    return Agent(
        role="Research Planner",
        goal="Ensure comprehensive coverage of the research topic by breaking down queries into sub-questions",
        backstory="You are an expert research strategist. Your job is to analyze a user query and determine the 3-5 most critical sub-questions needed to thoroughly research the topic.",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_crawler_agent(llm) -> Agent:
    return Agent(
        role="Web Crawler",
        goal="Retrieve raw, relevant, multi-source web content by executing searches and fetching page text",
        backstory="You are an expert web crawler and information retriever. You perform targeted searches and extract the actual contents of web pages to gather raw intelligence.",
        llm=llm,
        tools=[tavily_search, fetch_page_content],
        verbose=True,
        allow_delegation=False,
    )


def create_analyst_agent(llm) -> Agent:
    return Agent(
        role="Analyst",
        goal="Produce a structured analysis with source citations and confidence scores by cross-referencing and scoring crawled sources",
        backstory="You are a meticulous data and research analyst. You filter out noise, evaluate the credibility of sources, cross-reference facts, and assign confidence scores to findings.",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_writer_agent(llm) -> Agent:
    return Agent(
        role="Briefing Writer",
        goal="Produce a clean, structured markdown briefing with inline citations and a sources list",
        backstory="You are a professional executive writer. You take complex analysis and synthesize it into clear, concise, polished, executive-level briefings with proper sources listed.",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
