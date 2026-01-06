import asyncio
import signal
from dotenv import load_dotenv
    

class LoopState:
    """State for the main loop."""
    def __init__(self):
        self.stop = asyncio.Event()

async def poll(state: LoopState):
    """Poll data from the Vallox device."""
    print("Starting polling task...")
    while not state.stop.is_set():
        # Placeholder for polling logic
        print("Polling device...")
        await asyncio.sleep(5)  # Simulate polling 
    print("Polling task stopped.")


async def run_tasks(state: LoopState):
    """Create asyncio tasks for the main loop."""
    tasks = []
    tasks.append(asyncio.create_task(poll(state)))
    await asyncio.gather(*tasks)

def main():
    """Entry point for running the application."""
    load_dotenv()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    state = LoopState()

    def shutdown_handler():
        print("Shutdown signal received.")
        loop.call_soon_threadsafe(state.stop.set)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_handler)
    except NotImplementedError:
        signal.signal(signal.SIGINT, lambda *_: shutdown_handler())
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, lambda *_: shutdown_handler())
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, lambda *_: shutdown_handler())

    try:
        loop.run_until_complete(run_tasks(state))
    finally:
        loop.close()

if __name__ == "__main__":
    main()
        