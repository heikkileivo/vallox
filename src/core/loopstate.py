"""Shared state for the main loop."""
import asyncio

class LoopState:
    """Shared state for the main loop."""
    def __init__(self):
        self.stop = asyncio.Event()
        self.mqtt_connected = asyncio.Event()
        self.mqtt_client = None
        self.socket = None
        self.event_loop = None
        self.devices = None
        self.device_manager = None
        
