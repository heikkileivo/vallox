"""Main application entry point for Vallox MQTT integration."""

import asyncio
import json
import signal
import sys
import uuid
from os import environ as env
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from ha import TestDevice        

class LoopState:
    """State for the main loop."""
    def __init__(self):
        self.stop = asyncio.Event()
        self.mqtt_client = None
        self.socket = None
        self.event_loop = None
        self.device = None
        self.mqtt_connected = asyncio.Event()


async def poll(state: LoopState):
    """Poll data from the Vallox device."""
    print("Starting polling task...")
    while not state.stop.is_set():
        # Placeholder for polling logic
        state.device.temperature += 0.1  # Simulate temperature change
        try:
            for topic, payload in state.device.payloads:
                state.mqtt_client.publish(topic, json.dumps(payload), qos=0, retain=False)
        except Exception as e:
            print(f"Error publishing payloads: {e}")

        print("Polling device...")
        await asyncio.sleep(5)  # Simulate polling 
    print("Polling task stopped.")

def connect_mqtt(state: LoopState, on_connected, on_disconnected, on_message_received):
    """Connect to the MQTT broker."""
    def handle_read():
        state.mqtt_client.loop_read()

    def handle_write():
        state.mqtt_client.loop_write()

    def on_socket_open(client, userdata, sock):
        state.socket = sock
        state.event_loop.add_reader(sock.fileno(), handle_read)

    def on_socket_close(client, userdata, sock):
        if state.socket:
            try:
                state.event_loop.remove_reader(state.socket.fileno())
            except Exception:
                pass
        state.socket = None

    def on_socket_register_write(client, userdata, sock):
        state.event_loop.add_writer(sock.fileno(), handle_write)

    def on_socket_unregister_write(client, userdata, sock):
        try: 
            state.event_loop.remove_writer(sock.fileno())
        except Exception: 
            pass

    def on_connect(client, userdata, flags, rc):
        print(f"Connected to MQTT Broker with result code {rc}")
        state.mqtt_connected.set()
        on_connected(client)

    def on_disconnect(client, userdata, rc):
        print(f"Disconnected from MQTT Broker with result code {rc}")
        state.mqtt_connected.clear()
        on_disconnected(client)

    def on_message(client, userdata, msg):
        print(f"Received message on {msg.topic}: {msg.payload}")
        on_message_received(msg)


    # Generatre uuid for client id


    state.mqtt_client = mqtt.Client(client_id=str(uuid.uuid4()))
    
    state.mqtt_client.on_connect = on_connect
    state.mqtt_client.on_disconnect = on_disconnect
    state.mqtt_client.on_message = on_message
    state.mqtt_client.on_socket_open = on_socket_open
    state.mqtt_client.on_socket_close = on_socket_close
    state.mqtt_client.on_socket_register_write = on_socket_register_write
    state.mqtt_client.on_socket_unregister_write = on_socket_unregister_write
    state.mqtt_client.username_pw_set(env.get("MQTT_USERNAME"), env.get("MQTT_PASSWORD"))
    
    

async def misc_task(state: LoopState):
    """Task to handle MQTT miscellaneous loop."""
    print("Starting MQTT misc loop...")
    try:
        while state.stop.is_set() is False:
            state.mqtt_client.loop_misc()
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    print("MQTT misc loop stopped.")

async def mqtt_supervisor(state: LoopState):
    """Supervise MQTT connection."""
    print("Starting MQTT supervisor...")

    subscriptions = {}
    def on_connected(client):
        for topic, setter in state.device.subscriptions:
            subscriptions[topic] = setter
            client.subscribe(topic)

        topic = state.device.discovery_topic
        payload = json.dumps(state.device.discovery_payload)
        client.publish(topic, payload, qos=0, retain=True)
        
    def on_disconnected(client):
        print("MQTT disconnected callback.")
    
    def on_message(msg):
        setter = subscriptions.get(msg.topic, None)
        if setter:
            setter(msg.payload.decode())

    connect_mqtt(state, 
                 on_connected, 
                 on_disconnected,
                 on_message)

    
    initial_connect = True
    try:
        while state.stop.is_set() is False:
            if state.mqtt_connected.is_set():
                await asyncio.sleep(10.0)
                continue
            try:
                if initial_connect:
                    state.mqtt_client.connect(env.get("MQTT_HOST"),
                                                int(env.get("MQTT_PORT", 1883)),
                                                int(env.get("MQTT_KEEPALIVE", 60)))
                    print("Initial MQTT connection successful.")
                    initial_connect = False
                else:
                    state.mqtt_client.reconnect()
                    print("Reconnecting MQTT server successful.")        
            except Exception as e:
                print(f"MQTT reconnect failed: {e}")
            await asyncio.sleep(10.0)
    except asyncio.CancelledError:
        pass
    print("MQTT supervisor stopped.")


async def run_tasks(state: LoopState):
    """Create asyncio tasks for the main loop."""
    tasks = []
    tasks.append(asyncio.create_task(mqtt_supervisor(state)))
    tasks.append(asyncio.create_task(misc_task(state)))
    tasks.append(asyncio.create_task(poll(state)))
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
    state.device = TestDevice(serial_number="123456789")

    

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
        