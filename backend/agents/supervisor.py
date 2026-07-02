import os
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field


class RouteResponse(BaseModel):
    next: Literal["browser", "calendar", "research", "finish"] = Field(
        description="The next agent to route to, or 'finish' if the user's task is fully completed."
    )
    instructions: str = Field(
        description="Specific instructions for the target agent on what to do next, or the final response if finishing."
    )


GROQ_MODELS = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen-2.5-32b",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "deepseek-r1-distill-llama-70b",
}

def get_supervisor_chain(model_name: str = "llama-3.3-70b-versatile"):
    """Creates the supervisor routing chain, configured with a dynamic model chosen by the AI Router."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not configured in .env file.")

    print(f"Supervisor: Routing to Groq using model '{model_name}'...")
    llm = ChatGroq(model=model_name, temperature=0, api_key=api_key)

    structured_llm = llm.with_structured_output(RouteResponse)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Supervisor Agent for OmniPilot AI. Your job is to orchestrate a multi-agent "
                "system to fulfill the user's request. You have three specialized agents at your disposal:\n"
                "1. 'browser': For searching the web, browsing websites, fetching info.\n"
                "2. 'calendar': For checking availability and managing schedule events.\n"
                "3. 'research': For performing deep market topics or briefing prep.\n\n"
                "Analyze the conversation history. Decide if you need to route to 'browser', 'calendar', 'research', "
                "or if the task is completely finished, route to 'finish'.\n"
                "Note: If the 'research' agent has already executed and generated the briefing, the research task is completed. "
                "Do not route back to 'research' to ask for the briefing text, as it is automatically shown to the user on the dashboard. "
                "Instead, route to 'finish' (or 'calendar' if the user requested scheduling as a next step).\n"
                "Provide clear, concise instructions for the next agent.",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    return prompt | structured_llm
