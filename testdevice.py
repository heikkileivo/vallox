"""Example test device implementation."""

import asyncio
from device import Device, number, temperature
from loopstate import LoopState

class TestDevice(Device):
    """
    Example device for testing purposes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._name = "foo"
        self._temperature = 25.0
        self._speed = 0.0

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @name.setter
    def name(self, value: str):
        """Set the name of the device."""
        self._name = value

    @temperature(unit="°C")
    def temperature(self) -> float:
        """Return the temperature value."""
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        """Set the temperature value."""
        self._temperature = value

    @number(min_value=0, max_value=10, step=1)
    def speed(self) -> float:
        """Return the speed value."""
        return self._speed

    @speed.setter
    def speed(self, value: float):
        """Set the speed value."""
        self._speed = value

async def poll_device(state: LoopState, device: TestDevice):
    """Poll data from the device."""
    print("Starting polling task...")
    while not state.stop.is_set():
        # Placeholder for polling logic
        device.temperature += 0.1  # Simulate temperature change

        print("Polling device...")
        await asyncio.sleep(5)  # Simulate polling 
    print("Polling task stopped.")

def create_devices():
    """Create and return a list of test devices and their polling functions."""
    return [(TestDevice(root_topic="test_devices"), poll_device)]

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()
    td = TestDevice(root_topic="test_devices", 
                    device_id="test_device_1")

    print(type(TestDevice.speed))
    print(type(TestDevice.temperature))
    print(f"Temperature: {td.temperature} °C")
    print("Discovery topic:")
    print(td.discovery_topic)
    print("Discovery Config:")
    print(json.dumps(td.discovery_payload, indent=4))
    print("Value Topic:")
    print(td.value_topic)
    print("Value Payload:")
    print(json.dumps(td.payloads, indent=4))
    print("Subscriptions:")
    for topic, setter in td.subscriptions:
        print(f"Topic: {topic}, Setter: {setter}")
    print("Setting new speed to 5...")
    td.speed = 5
    print(f"New Speed: {td.speed}")

