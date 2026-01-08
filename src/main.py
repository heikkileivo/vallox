"""Main application entry point for Vallox MQTT integration."""

import asyncio
import signal
import sys
import os
from os import environ as env
import importlib
from typing import Callable, List, Tuple
from dotenv import load_dotenv
from core import DeviceManager, Device
from core import LoopState
from core import misc_task, mqtt_supervisor

create_devices: List[Callable[[], List[Tuple[Device, Callable]]]] = []

async def run_tasks(state: LoopState):
    """Create asyncio tasks for the main loop."""
    tasks = []

    def on_connected(client):
        state.mqtt_connected.set()
        state.device_manager.mqtt_client = client
        state.device_manager.subscribe_all()
        state.device_manager.publish_discovery_topics()
        state.device_manager.publish_all()

    def on_disconnected(_client):
        state.mqtt_connected.clear()
        state.device_manager.mqtt_client = None

    def on_message(msg):
        state.device_manager.handle_message(msg)

    tasks.append(asyncio.create_task(mqtt_supervisor(state, 
                                                  on_connected, 
                                                  on_disconnected,
                                                  on_message)))

    tasks.append(asyncio.create_task(misc_task(state)))

    for create_devices_func in create_devices:
        devices = create_devices_func()
        for device, task in devices:  
            state.device_manager.add_device(device)
            tasks.append(asyncio.create_task(task(state, device)))

    await asyncio.gather(*tasks)

def main():
    """Entry point for running the application."""

    load_dotenv()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    state = LoopState()
    state.event_loop = loop
    state.device_manager = DeviceManager()    

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
    module_names_env = env.get("DEVICE_MODULES", None)
    if not module_names_env:
        print("Error: DEVICE_MODULES environment variable is not set.")
        print("Set it to one or more module names separated by spaces.")
        print("Example: DEVICE_MODULES='module1 module2'")
        sys.exit(1)

    module_names = module_names_env.split()
    
    for module_name in module_names:
        try:
            device_module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"Error importing module '{module_name}': {e}")
            exit(1)

        if hasattr(device_module, "create_devices"):
            create_devices.append(device_module.create_devices)
            print(f"Loaded module: {module_name}")
        else:
            print(f"Warning: Module '{module_name}' does not have 'create_devices' function.")

    if not create_devices:
        print("Error: No valid modules with 'create_devices' function found.")
        exit(1)

    main()
