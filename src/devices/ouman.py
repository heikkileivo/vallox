"""Ouman device implementation."""

import asyncio
import struct
from os import environ as env
from logging import debug
import serial
from core import Device
from core.loopstate import LoopState
from core.sensors import temperature, numeric, binary


class MeasurePoint:
    """Measure point as defined in the Ouman XML config file."""
    def __init__(self, index, mask, name, datastart, dataend, unit, divisor, parent):
        self.idx = index
        self.mask = mask
        self.name = name
        self.datastart = datastart
        self.dataend = dataend
        self.unit = unit
        self.divisor = divisor
        self.__ouman = parent
        self._raw_value = None
        self._value = None

    def read(self):
        """Read the value of this measure point from the Ouman device."""
        self._raw_value = self.__ouman.read(self)
        new_value = self.parse(self._raw_value)
        if new_value != self._value:
            self._value = new_value
            self.__ouman.on_property_changed(self.name, self._value)

    @property
    def raw_value(self):
        """Return the raw value as read from the device."""
        return self._value
    
    @property
    def value(self):
        """Return the parsed value."""
        return self._value
    
    def parse(self, raw_value):
        """Parse the raw value to the appropriate type."""
        return raw_value

class Flags:
    """
    Binary data measure point as defined in the Ouman XML config file.
    The intent of this class is to read flags only once per cycle.
    """
    
    def __init__(self, raw_value):
        self.raw_value = raw_value
    
    @property
    def bit1(self):
        """Return the state of bit 1."""
        return bool(self.raw_value & 1)
    
    @property
    def bit2(self):
        """Return the state of bit 2."""
        return bool(self.raw_value & 2)
    
    @property
    def bit3(self):
        """Return the state of bit 3."""
        return bool(self.raw_value & 4)
    
    @property
    def bit4(self):
        """Return the state of bit 4."""
        return bool(self.raw_value & 8)
    
    @property
    def bit5(self):
        """Return the state of bit 5."""
        return bool(self.raw_value & 16)

    @property
    def bit6(self):
        """Return the state of bit 6."""
        return bool(self.raw_value & 32)
    
    @property
    def bit7(self):
        """Return the state of bit 7."""
        return bool(self.raw_value & 64)
    
    @property
    def bit8(self):
        """Return the state of bit 8."""
        return bool(self.raw_value & 128)


class BinaryMeasurePoint(MeasurePoint):
    """Binary measure point as defined in the Ouman XML config file."""
    
    def parse(self, raw_value):
        """Parse the raw value to a boolean."""
        if raw_value is None:
            return None
        return bool(raw_value & self.mask)

class FlagsMeasurePoint(MeasurePoint):
    """Binary measure point as defined in the Ouman XML config file."""
    
    def parse(self, raw_value):
        """Parse the raw value to a boolean."""
        if raw_value is None:
            return None
        return Flags(raw_value)

class NumericMeasurePoint(MeasurePoint):
    """Numeric measure point as defined in the Ouman XML config file."""
    
    def parse(self, raw_value):
        return float(raw_value) / self.divisor if raw_value is not None else None
    
class Ouman(Device):
    """Base class for Ouman devices."""
    STX = b'\x02'
    ACK = b'\x06'

    def __init__(self, points,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__serio = None
        self.__measurepoints = {mp.name: mp for mp in points}

    def connect(self, dev, baudrate=4800, timeout=1):
        """Connect to the Ouman device via serial port."""
        self.__serio = serial.Serial(dev, baudrate, timeout=timeout)
        self.__serio.reset_input_buffer()
        self.__serio.reset_output_buffer()

    def close(self):
        """Close the connection to the Ouman device."""
        self.__serio.close()
    
    def read_all(self):
        """Read all measure points from the Ouman device."""
        for mp in self.__measurepoints.values():
            mp.read()

    def read(self, measurepoint):
        """Read a measure point from the Ouman device."""
        return self.__read(measurepoint.idx, measurepoint.datastart, measurepoint.dataend)

    def __read(self, cmd, s, e):
        debug('reading id %i', cmd)
        buf = self.__fmt_cmd(cmd)
        debug('sending %s', buf)
        self.__serio.write(buf)
        self.__serio.flush()

        # First two bytes should be STX+ACK
        stx = self.__serio.read()
        if stx != self.STX:
            return None
        ack = self.__serio.read()
        if ack != self.ACK:
            debug('serio failed: %s', ack)
            return None

        datalen = self.__serio.read()
        try:
            n, = struct.unpack('B', datalen)
            debug('datalen = %i', n)
        except Exception as _:
            debug(f'Getting data length failed: datalen = {datalen}')
            return None

        data = self.__serio.read(n)
        checksum = self.__serio.read()
        crc = self.__calc_crc(ack + datalen + data)
        if not checksum or crc != checksum:
            debug('checksum failed: %s != %s', crc, checksum)
            return None

        debug('data = %s', repr(data))
        cmd_str, data = data[0:2], data[2:]
        cmd2, = struct.unpack('!h', cmd_str)
        if cmd2 != cmd:
            debug('command failed: %s != %s', cmd2, cmd)
            return None

        data = data[s:e + 1]
        value_len = e - s + 1
        unpack_fmt = {1: 'b', 2: '!h', 4: '!i'}[value_len]
        debug('unpacking %s with value_len = %i and unpack_fmt = %s', data, value_len, unpack_fmt)
        val, = struct.unpack(unpack_fmt, data)

        return val

    def __calc_crc(self, data):
        # crc is just an 8-bit sum
        data = struct.unpack('B' * len(data), data)
        crc = struct.pack('B', sum(data) & 0xff)
        return crc

    def __fmt_cmd(self, cmd):
        cmd = struct.pack('!h', cmd)  # commands are 16 bit
        header = b'\x81' + bytearray((len(cmd),))
        crc = self.__calc_crc(header + cmd)
        return self.STX + header + cmd + crc
    
    async def poll_device(self, state: LoopState):
        """Poll data from the device."""
        print("Starting Ouman polling task...")
        try:

            port = env.get("OUMAN_SERIAL_PORT", "/dev/ttyUSB0")
            print(f"Connecting Ouman device on port {port}...")
            self.connect(port)
            print("Ouman device connected.")

            await asyncio.sleep(2)  # Wait for the connection to stabilize
        except Exception as e:
            print(f"Failed to connect to Ouman device: {e}")
            return
        
        while not state.stop.is_set():
            try:
                self.read_all()
            except Exception as e:
                print(f"Error while reading from Ouman device: {e}")
            await asyncio.sleep(1)  
        print("Polling Ouman stopped.")

    def get_measurepoint(self, name):
        """Get a measure point by name."""
        return self.__measurepoints.get(name)   

class OumanEH203(Ouman):
    """Ouman EH-203 device implementation."""
    def __init__(self, *args, **kwargs):
        points = []
        # Define measure points for Ouman EH-203 based on EH-203.xml
        # Analog measurements
        points.append(NumericMeasurePoint(18, 0, "outdoor_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(20, 0, "h1_supply_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(21, 0, "h1_room_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(23, 0, "h1_return_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(26, 0, "h2_supply_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(27, 0, "measurement_6", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(24, 0, "hw_supply_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(25, 0, "hw_circulation_temperature", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(33, 0, "measurement_9", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(34, 0, "measurement_10", 0, 1, "C", 100, self))
        points.append(NumericMeasurePoint(41, 0, "measurement_11", 0, 1, "C", 100, self))

        # Digital inputs
        points.append(BinaryMeasurePoint(45, 1, "digital_input1", 0, 1, "dig", 1, self))
        points.append(BinaryMeasurePoint(45, 2, "digital_input2", 0, 1, "dig", 1, self))
        points.append(BinaryMeasurePoint(45, 4, "digital_input3", 0, 1, "dig", 1, self))

        # Relays
        points.append(BinaryMeasurePoint(45, 8, "relay1", 0, 1, "dig", 1, self))
        points.append(BinaryMeasurePoint(45, 16, "relay2", 0, 1, "dig", 1, self))

        # Valve positions
        points.append(NumericMeasurePoint(49, 0, "h1_valve_position", 0, 0, "%", 1, self))
        points.append(NumericMeasurePoint(50, 0, "h2_valve_position", 0, 0, "%", 1, self))
        points.append(NumericMeasurePoint(51, 0, "hw_valve_position", 0, 0, "%", 1, self))

        # Setpoints
        points.append(NumericMeasurePoint(13, 0, "h1_room_setpoint", 1, 2, "C", 10, self))
        points.append(NumericMeasurePoint(13, 0, "h2_room_setpoint", 11, 12, "C", 10, self))
        points.append(NumericMeasurePoint(15, 0, "hw_supply_setpoint", 15, 15, "C", 1, self))

        # Energy measurements
        points.append(NumericMeasurePoint(60, 0, "peak_power", 0, 3, "kWh", 1, self))
        points.append(NumericMeasurePoint(61, 0, "peak_flow", 0, 3, "m3", 100, self))
        points.append(NumericMeasurePoint(63, 0, "hw_energy", 0, 3, "kWh", 1, self))
        points.append(NumericMeasurePoint(64, 0, "hw_water", 0, 3, "m3", 100, self))
        
        super().__init__(points, *args, **kwargs)


    @temperature(unit="°C", display_name="Outdoor Temperature")
    def outdoor_temperature(self):
        """Return the outdoor temperature measure point value."""
        return self.get_measurepoint('outdoor_temperature').value
    
    @temperature(unit="°C", display_name="H1 Supply Temperature")
    def h1_supply_temperature(self):
        """Return the H1 supply temperature measure point value."""
        return self.get_measurepoint('h1_supply_temperature').value

    @temperature(unit="°C", display_name="H1 Room Temperature")
    def h1_room_temperature(self):
        """Return the H1 room temperature measure point value."""
        return self.get_measurepoint('h1_room_temperature').value
    
    @temperature(unit="°C", display_name="H1 Return Temperature")
    def h1_return_temperature(self):
        """Return the H1 return temperature measure point value."""
        return self.get_measurepoint('h1_return_temperature').value
    
    @temperature(unit="°C", display_name="H2 Supply Temperature")
    def h2_supply_temperature(self):
        """Return the H2 supply temperature measure point value."""
        return self.get_measurepoint('h2_supply_temperature').value

    @numeric(display_name="Measurement 6")
    def measurement_6(self):
        """Return the measurement 6 measure point value."""
        return self.get_measurepoint('measurement_6').value
    
    @temperature(unit="°C", display_name="HW Supply Temperature")
    def hw_supply_temperature(self):
        """Return the HW supply temperature measure point value."""
        return self.get_measurepoint('hw_supply_temperature').value
    
    @temperature(unit="°C", display_name="HW Circulation Temperature")
    def hw_circulation_temperature(self):
        """Return the HW circulation temperature measure point value."""
        return self.get_measurepoint('hw_circulation_temperature').value
    
    @numeric(display_name="Measurement 9")
    def measurement_9(self):
        """Return the measurement 9 measure point value."""
        return self.get_measurepoint('measurement_9').value
    
    @numeric(display_name="Measurement 10")
    def measurement_10(self):
        """Return the measurement 10 measure point value."""
        return self.get_measurepoint('measurement_10').value
    
    @numeric(display_name="Measurement 11")
    def measurement_11(self):
        """Return the measurement 11 measure point value."""
        return self.get_measurepoint('measurement_11').value    

    @binary(display_name="Digital Input 1")
    def digital_input1(self):
        """Return the state of digital input 1."""
        return self.get_measurepoint('digital_input1').value
    
    @binary(display_name="Digital Input 2")
    def digital_input2(self):
        """Return the state of digital input 2."""
        return self.get_measurepoint('digital_input2').value
    
    @binary(display_name="Digital Input 3")
    def digital_input3(self):
        """Return the state of digital input 3."""
        return self.get_measurepoint('digital_input3').value
    
    @binary(display_name="Relay 1")
    def relay1(self):
        """Return the state of relay 1."""
        return self.get_measurepoint('relay1').value
    
    @binary(display_name="Relay 2")
    def relay2(self):
        """Return the state of relay 2."""
        return self.get_measurepoint('relay2').value
    
    @numeric(unit="%", display_name="H1 Valve Position")
    def valve1_position(self):
        """Return the H1 valve position measure point value."""
        return self.get_measurepoint('h1_valve_position').value
    
    @numeric(unit="%", display_name="H2 Valve Position")
    def valve2_position(self):
        """Return the H2 valve position measure point value."""
        return self.get_measurepoint('h2_valve_position').value
    
    @numeric(unit="%", display_name="HW Valve Position")
    def hw_valve_position(self):
        """Return the HW valve position measure point value."""
        return self.get_measurepoint('hw_valve_position').value


    @temperature(unit="°C", display_name="H1 Room Setpoint")
    def h1_room_setpoint(self):
        """Return the H1 room setpoint measure point value."""
        return self.get_measurepoint['h1_room_setpoint'].value
    

    @temperature(unit="°C", display_name="H2 Room Setpoint")
    def h2_room_setpoint(self):
        """Return the H2 room setpoint measure point value."""
        return self.get_measurepoint('h2_room_setpoint').value
    

    @temperature(unit="°C", display_name="HW Supply Setpoint")
    def hw_supply_setpoint(self):
        """Return the HW supply setpoint measure point value."""
        return self.get_measurepoint('hw_supply_setpoint').value

    @numeric(unit="kW", display_name="Peak Power")
    def peak_power(self):
        """Return the peak power measure point value."""
        return self.get_measurepoint('peak_power').value 
    
    @numeric(unit="m3", display_name="Peak Flow")
    def peak_flow(self):
        """Return the peak flow measure point value."""
        return self.get_measurepoint('peak_flow').value

    @numeric(unit="kWh", display_name="HW Energy")
    def hw_energy(self):
        """Return the HW energy measure point value."""
        return self.get_measurepoint('hw_energy').value
    
    @numeric(unit="m3", display_name="HW Water")
    def hw_water(self):
        """Return the HW water measure point value."""
        return self.get_measurepoint('hw_water').value

def create_devices():
    """Create and return a list of Ouman devices."""
    return [OumanEH203(root_topic="heating_controls",
                       manufacturer="Ouman",
                       model="EH-203",
                       serial_number="EH203-001")]
