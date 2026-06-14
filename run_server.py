import sys
import asyncio

# Force event loop policy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

async def main():
    config = uvicorn.Config(
        "backend.main:app", 
        host="127.0.0.1", 
        port=8000, 
        log_level="info",
        loop="asyncio"  # Tells uvicorn to use standard asyncio loop (respecting our policy)
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
