import asyncio
import os
from langchain_core.messages import HumanMessage
from backend.workflows.agent_graph import compiled_graph

# Ensure backend package can be imported if running directly
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def run_test(query: str):
    print(f"\n=========================================")
    print(f"Testing Query: '{query}'")
    print(f"=========================================")
    
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "next": "supervisor"
    }
    
    async for event in compiled_graph.astream(initial_state):
        for node_name, output in event.items():
            print(f"\n[Node: {node_name}] outputted changes:")
            for msg in output.get("messages", []):
                print(f"  - {msg.name}: {msg.content}")

async def main():
    # Test Browser fallback routing
    await run_test("Find a good Italian restaurant nearby.")
    
    # Test Calendar fallback routing
    await run_test("Book a meeting on my calendar for tomorrow at 2 PM.")

if __name__ == "__main__":
    asyncio.run(main())
