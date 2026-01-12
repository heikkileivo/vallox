"""
MQTT discovery for Home Assistant integration.
"""
from typing import ClassVar, Dict, List, Tuple, Optional
import os
from os import environ as env


class DeviceId:
    """
    Generate and persist unique IDs for devices.
    """
    _index : int = 0
    _is_initialized : bool = False
    _ids : ClassVar[List[str]] = []

    """ Class initializer to load existing IDs from file. """
    @classmethod
    def _initialize(cls):
        if not cls._is_initialized:
            try:
                with open("deviceids.txt", "r", encoding="utf-8") as f:
                    cls._ids = [line.strip() for line in f.readlines()]
            except FileNotFoundError:
                cls._ids = []
            cls._is_initialized = True


    @classmethod
    def get_next(cls) -> str:
        """ Get the next unique device ID. """
        if not cls._is_initialized:
           cls._initialize()
        if cls._index < len(cls._ids):
            device_id = cls._ids[cls._index]
            cls._index += 1
            return device_id
        else:
            # Generate new, random 16-digit hex ID
            new_id = f"0x{ hex(int.from_bytes(os.urandom(8), 'big'))[2:].rjust(16, '0')}"
            cls._ids.append(new_id)
            cls._index += 1
            with open("deviceids.txt", "a", encoding="utf-8") as f:
                f.write(new_id + "\n")
            return new_id
        

class DeviceProperty(property):
    """
    Represents a property of a Home Assistant device.
    Properties are serialized as json for MQTT auto-discovery.
    """
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        self._name: str = ""
        self.parent = None
        self.display_name: Optional[str] = None
        self.type: Optional[type] = None

    @property
    def is_read_only(self) -> bool:
        """Return True if the property is read-only."""
        return self.fset is None

    def __set_name__(self, owner, name: str) -> None:
        # Called when the descriptor is assigned to a class attribute
        instance = self
        while True:
            instance._name = name
            instance = instance.parent
            if instance is None: 
                break

    def serialize(self, value) -> str:
        """Serialize the property value to a string."""
        return str(value)

    def parse(self, value: str):
        """Parse the property value from a string."""
        return self.type(value) if self.type else value

    def discovery_payload(self, _device: "Device") -> dict:
        """Return metadata for temperature property."""
        return {}

    def _copy_metadata_to(self, other: "DeviceProperty") -> "DeviceProperty":
        other.display_name = self.display_name
        return other

    def _replace(self, fget=None, fset=None, fdel=None, doc=None):
        new = type(self)(fget, fset, fdel, doc)
        new.parent = self
        return self._copy_metadata_to(new)

    def getter(self, fget):
        return self._replace(fget=fget, fset=self.fset, fdel=self.fdel, doc=self.__doc__)

    def setter(self, fset):
        def new_setter(instance, value):
            fset(instance, value)
            instance.on_property_changed(self._name, value)

        return self._replace(fget=self.fget, fset=new_setter, fdel=self.fdel, doc=self.__doc__)

    def deleter(self, fdel):
        def new_deleter(instance):
            fdel(instance)
            instance.on_property_changed(self._name, None)
        return self._replace(fget=self.fget, fset=self.fset, fdel=new_deleter, doc=self.__doc__)


class DeviceMetaclass(type):
    """
    Metaclass for Home Assistant MQTT discovery devices.
    """

    def __new__(mcs, name, bases, attrs):
        components = {}
        for b in bases:
            components.update(getattr(b, "components", {}))

        for key, value in attrs.items():
            if isinstance(value, DeviceProperty):
                components[key] = value

        attrs["components"] = components
        return super().__new__(mcs, name, bases, attrs)

class Device(metaclass=DeviceMetaclass):
    """
    Base class for Home Assistant MQTT discovery devices.
    """
    components:  ClassVar[Dict[str, DeviceProperty]]
    def __init__(self, **kwargs):
        args = {**kwargs, **env}
        self.root_topic : str = args.get("root_topic", self.__class__.__name__.lower())
        self.discovery_prefix : str = args.get("discovery_prefix", "homeassistant")
        self.device_id : str = args.get("device_id", DeviceId.get_next())
        self.device_name : str = args.get("device_name", self.__class__.__name__)
        self.manufacturer : str = args.get("manufacturer", "Unknown")
        self.model : str = args.get("model", "Unknown")
        self.software_version : str = args.get("software_version", "1.0")
        self.serial_number : Optional[str] = args.get("serial_number", "")
        self.hardware_version : str = args.get("hardware_version", "1.0")
        self.origin: str = args.get("origin", "Unknown")
        self.support_url: str = args.get("support_url", "https://example.com/support")
        self.manager = None

    @property
    def discovery_topic(self) -> str:
        """Generate MQTT topic for Home Assistant discovery."""
        return f"{self.discovery_prefix}/device/{self.device_id}/config"

    @property
    def discovery_payload(self) -> dict:
        """Generate MQTT discovery configuration for Home Assistant."""
        dev = {"ids": f"{self.device_id}",
               "name": f"{self.device_name}",
               "mf": f"{self.manufacturer}",
               "mdl": f"{self.model}",
               "sw": f"{self.software_version}",
               "sn": self.serial_number,
               "hw": f"{self.hardware_version}",
               }

        o = {"name": f"{self.origin}", 
             "sw": f"{self.software_version}", 
             "url": f"{self.support_url}"}

        cmps = {f"{self.device_id}_{n}": c.discovery_payload(self) for n, c in self.components.items()}
        return {"dev": dev, 
                "o": o, 
                "cmps": cmps, 
                "state_topic": f"{self.device_id}/state", 
                "qos": 0 }

    @property
    def availability_topic(self) -> str:
        """Generate MQTT topic for device availability."""
        return f"{self.root_topic}/{self.device_id}/availability"

    @property
    def value_topic(self) -> str:
        """Generate MQTT topic for device state."""
        return f"{self.root_topic}/{self.device_id}/state"

    @property
    def payloads(self):
        """Publish the values to mqtt server."""
        components = self.__class__.__dict__.get("components", {})
        payloads =  [(f"{self.root_topic}/{self.device_id}/{k.lower()}/state", v.serialize(v.fget(self)) if v.fget(self) else None)
                     for k, v in components.items()]
        payloads = [(t, p) for t, p in payloads if p is not None]
        return payloads

    @property
    def subscriptions(self) -> List[Tuple[str, int]]:
        """Generate MQTT subscriptions for command topics."""
        subs = []

        def create_setter(prop):
            def s(payload):
                print("Setting property via MQTT:", payload)
                prop.fset(self, prop.parse(payload))
            return s

        for name, prop in self.components.items():
            if prop.is_read_only:
                continue

            t = f"{self.root_topic}/{self.device_id}/{name.lower()}/set"
            subs.append((t, create_setter(prop)))
        return subs

    def on_property_changed(self, name, value):
        """Callback when a property value changes."""
        if value is None:
            return
        print(f"Property changed: {name}, New Value: {value}")
        if self.manager and self.manager.mqtt_client:
            prop = self.components.get(name)
            if prop is None:
                return
            topic = f"{self.root_topic}/{self.device_id}/{name.lower()}/state"
            payload = prop.serialize(value)
            try:
                self.manager.mqtt_client.publish(topic, str(payload), qos=0, retain=False)
                print(f"Published updated value to {topic}: {payload}")
            except Exception as e:
                print(f"Error publishing updated value: {e}")
