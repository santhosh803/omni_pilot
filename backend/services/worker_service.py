import asyncio

# In-process asynchronous queue for background jobs (Phase 3)
BACKGROUND_QUEUE = asyncio.Queue()

async def worker_loop():
    """Background worker process pulling and executing jobs from the queue."""
    print("Background Worker: Listening for tasks...")
    while True:
        try:
            job = await BACKGROUND_QUEUE.get()
            func, args, kwargs = job
            print(f"Background Worker: Executing job '{func.__name__}'...")
            
            # Execute task
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
                
            print(f"Background Worker: Finished job '{func.__name__}'")
        except asyncio.CancelledError:
            print("Background Worker: Shutting down worker listener.")
            break
        except Exception as e:
            print(f"Background Worker Exception: {e}")
        finally:
            BACKGROUND_QUEUE.task_done()

def enqueue_background_job(func, *args, **kwargs):
    """Enqueues a task to the background processor."""
    BACKGROUND_QUEUE.put_nowait((func, args, kwargs))
    print(f"Background Worker: Task '{func.__name__}' added to queue.")
