import asyncio

# In-process asynchronous queue for background jobs (Phase 3)
BACKGROUND_QUEUE: asyncio.Queue = asyncio.Queue()
CURRENT_LOOP = None


def get_background_queue():
    """Helper to get the background queue, recreating it if the running event loop changed."""
    global BACKGROUND_QUEUE, CURRENT_LOOP
    try:
        loop = asyncio.get_running_loop()
        if CURRENT_LOOP is None or CURRENT_LOOP != loop:
            BACKGROUND_QUEUE = asyncio.Queue()
            CURRENT_LOOP = loop
    except RuntimeError:
        pass
    return BACKGROUND_QUEUE


async def worker_loop():
    """Background worker process pulling and executing jobs from the queue."""
    print("Background Worker: Listening for tasks...")
    while True:
        queue = get_background_queue()
        retrieved = False
        try:
            job = await queue.get()
            retrieved = True
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
            if retrieved:
                queue.task_done()


def enqueue_background_job(func, *args, **kwargs):
    """Enqueues a task to the background processor."""
    queue = get_background_queue()
    queue.put_nowait((func, args, kwargs))
    print(f"Background Worker: Task '{func.__name__}' added to queue.")
