"""MQTT client setup and connection handling."""
import asyncio
import uuid
from os import environ as env
import paho.mqtt.client as mqtt
from .loopstate import LoopState

def create_mqtt_client(state: LoopState, on_connected, on_disconnected, on_message_received):
    """Connect to the MQTT broker."""
    def handle_read():
        state.mqtt_client.loop_read()

    def handle_write():
        state.mqtt_client.loop_write()

    def on_socket_open(_client, _userdata, sock):
        state.socket = sock
        state.event_loop.add_reader(sock.fileno(), handle_read)

    def on_socket_close(_client, _userdata, _sock):
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

async def mqtt_supervisor(state: LoopState, on_connected, on_disconnected, on_message):
    """Supervise MQTT connection."""
    print("Starting MQTT supervisor...")

    create_mqtt_client(state, 
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
