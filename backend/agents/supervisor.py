import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

class RouteResponse(BaseModel):
    next: Literal["browser", "calendar", "finish"] = Field(
        description="The next agent to route to, or 'finish' if the user's task is fully completed."
    )
    instructions: str = Field(
        description="Specific instructions for the target agent on what to do next, or the final response if finishing."
    )

def get_supervisor_chain():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        # Raise an error to let the fallback logic in agent_graph handle it
        raise ValueError("GROQ_API_KEY not configured in .env file.")
        
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=api_key
    )
    
    structured_llm = llm.with_structured_output(RouteResponse)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are the Supervisor Agent for OmniPilot AI. Your job is to orchestrate a multi-agent "
         "system to fulfill the user's request. You have two specialized agents at your disposal:\n"
         "1. 'browser': For searching the web, browsing websites, fetching information, booking, etc.\n"
         "2. 'calendar': For checking availability, creating, updating, or deleting calendar events.\n\n"
         "Analyze the conversation history. Decide if you need to route to 'browser', 'calendar', "
         "or if the task is completely finished, route to 'finish'.\n"
         "Provide clear, concise instructions for the next agent."),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    return prompt | structured_llm
