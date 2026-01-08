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

    def meta(self, _device: "Device") -> dict:
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

class Number(DeviceProperty):
    """
    Represents a numeric property of a Home Assistant device.
    """
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        self.type: type = int
        self.unit: str = ""
        self.min: Optional[float] = None
        self.max: Optional[float] = None
        self.step: Optional[float] = None

    def _copy_metadata_to(self, other: "Number") -> "Number":
        super()._copy_metadata_to(other)
        other.type = self.type
        other.unit = self.unit
        other.min = self.min
        other.max = self.max
        other.step = self.step
        return other

    def meta(self, device) -> dict:
        """
        Return metadata for number entity.
        """
        meta = {
            "name": self.display_name or self._name,
            "p": "number",
            "unit_of_measurement": self.unit,
            "state_topic": f"{device.root_topic}/{device.device_id}/{self._name.lower()}",
            "unique_id": f"{device.device_id}_{self._name.lower()}",
        }
        if self.is_read_only is False:
            meta["command_topic"] = f"{device.root_topic}/{device.device_id}/{self._name.lower()}/set"
        if self.min is not None:
            meta["min"] = self.min
        if self.max is not None:
            meta["max"] = self.max
        if self.step is not None:
            meta["step"] = self.step
        return meta

def number(value_type: type = int,
           display_name: str = "",
           unit: str = "",
           min_value: Optional[float] = None, 
           max_value: Optional[float] = None, 
           step: Optional[float] = None):
    """
    Decorator to define a numeric property.
    """
    def decorator(func):
        prop = Number(func)
        prop.display_name = display_name
        prop.type = value_type
        prop.unit = unit
        prop.min = min_value
        prop.max = max_value
        prop.step = step
        return prop
    return decorator

class Temperature(DeviceProperty):
    """
    Represents a temperature property of a Home Assistant device.
    """
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)
        self.type: type = float
        self.unit: str = "°C"

    def _copy_metadata_to(self, other):
        super()._copy_metadata_to(other)
        other.type = self.type
        other.unit = self.unit
        return other

    def meta(self, device) -> dict:
        """
        Return metadata for temperature entity.
        """
        return {
            "name": self.display_name or self._name,
            "p": "sensor",
            "unit_of_measurement": self.unit,
            "device_class": "temperature",
            "state_topic": f"{device.root_topic}/{device.device_id}/{self._name.lower()}",
            "unique_id": f"{device.device_id}_{self._name.lower()}",
        }

def temperature(unit: str = "°C", display_name: Optional[str] = None):
    """
    Decorator to define a temperature property.
    """
    def decorator(func):
        prop = Temperature(func)
        prop.unit = unit
        prop.display_name = display_name
        return prop
    return decorator

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
               "hw": f"{self.hardware_version}"}

        o = {"name": f"{self.origin}", 
             "sw": f"{self.software_version}", 
             "url": f"{self.support_url}"}

        cmps = {f"{self.device_id}_{n}": c.meta(self) for n, c in self.components.items()}
        return {"dev": dev, 
                "o": o, 
                "cmps": cmps, 
                "state_topic": f"{self.device_id}/state", 
                "qos": 0 }

    @property
    def value_topic(self) -> str:
        """Generate MQTT topic for device state."""
        return f"{self.root_topic}/{self.device_id}/state"

    @property
    def payloads(self):
        """Publish the values to mqtt server."""
        components = self.__class__.__dict__.get("components", {})
        payloads =  [(f"{self.root_topic}/{self.device_id}/{k}", v.fget(self))
                     for k, v in components.items()]
        return payloads

    @property
    def subscriptions(self) -> List[Tuple[str, int]]:
        """Generate MQTT subscriptions for command topics."""
        subs = []

        def create_setter(prop):
            def s(payload):
                print("Setting property via MQTT:", payload)
                prop.fset(self, prop.type(payload))
            return s

        for name, prop in self.components.items():
            if prop.is_read_only:
                continue

            t = f"{self.root_topic}/{self.device_id}/{name.lower()}/set"
            subs.append((t, create_setter(prop)))
        return subs

    def on_property_changed(self, name, value):
        """Callback when a property value changes."""
        print(f"Property changed: {name}, New Value: {value}")
        if self.manager and self.manager.mqtt_client:
            topic = f"{self.root_topic}/{self.device_id}/{name.lower()}"
            payload = value
            try:
                self.manager.mqtt_client.publish(topic, str(payload), qos=0, retain=False)
                print(f"Published updated value to {topic}: {payload}")
            except Exception as e:
                print(f"Error publishing updated value: {e}")
