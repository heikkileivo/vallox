"""
Vallox Digit SE Communication Library for Python

This module provides serial communication with Vallox air conditioning units.
Based on the original Arduino implementation by Toni Korhonen.
"""
import asyncio
import time
from typing import Optional, Callable, Any
from dataclasses import dataclass
from os import environ as env
import serial
from device import Device, temperature
from loopstate import LoopState
import vallox_protocol as vp


@dataclass
class ValueWithTimestamp:
    """Data structure to store value with timestamp"""
    value: Any = None
    last_received: float = 0.0

class Vallox(Device):
    """
    Vallox Digit SE serial communication handler

    This class handles serial communication with Vallox air conditioning units,
    providing methods to read status, temperatures, and control the device.

    See the original implementation by Toni Korhonen (@kotope) for reference:
    https://github.com/kotope/valloxesp/tree/master
    """

    def __init__(self,
                 port: str = "/dev/ttyUSB0",
                 baudrate: int = 9600,
                 debug: bool = False, **kwargs):
        """
        Initialize Vallox communication

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0' on Linux)
            baudrate: Serial baudrate (default: 9600)
            debug: Enable debug mode
        """
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self._debug = debug
        self.serial: Optional[serial.Serial] = None

        # Initialize data structures
        self.data = {
            'updated': 0.0,

            # Boolean status values
            'is_on': ValueWithTimestamp(),
            'is_rh_mode': ValueWithTimestamp(),
            'is_heating_mode': ValueWithTimestamp(),
            'is_filter': ValueWithTimestamp(),
            'is_heating': ValueWithTimestamp(),
            'is_fault': ValueWithTimestamp(),
            'is_service_needed': ValueWithTimestamp(),
            'is_summer_mode': ValueWithTimestamp(),
            'is_error_relay': ValueWithTimestamp(),
            'is_motor_in': ValueWithTimestamp(),
            'is_front_heating': ValueWithTimestamp(),
            'is_motor_out': ValueWithTimestamp(),
            'is_extra_func': ValueWithTimestamp(),
            'is_switch_active': ValueWithTimestamp(),

            # Temperature values
            'outside_temp': ValueWithTimestamp(),
            'inside_temp': ValueWithTimestamp(),
            'exhaust_temp': ValueWithTimestamp(),
            'incoming_temp': ValueWithTimestamp(),

            # Other sensor values
            'rh1': ValueWithTimestamp(),
            'rh2': ValueWithTimestamp(),
            'co2_hi': ValueWithTimestamp(),
            'co2_lo': ValueWithTimestamp(),
            'co2': ValueWithTimestamp(),

            # Configuration values
            'fan_speed': ValueWithTimestamp(),
            'default_fan_speed': ValueWithTimestamp(),
            'service_period': ValueWithTimestamp(),
            'service_counter': ValueWithTimestamp(),
            'heating_target': ValueWithTimestamp(),

            # Full byte messages
            'status': ValueWithTimestamp(),
            'variable08': ValueWithTimestamp(),
            'flags06': ValueWithTimestamp(),
        }

        # Settings
        self.settings = {
            'is_boost_setting': ValueWithTimestamp(),
            'program': ValueWithTimestamp(),
        }

        # State tracking
        self.full_init_done = False
        self.last_requested = 0.0
        self.last_retry_loop = 0.0
        self.status_mutex = False

        # Callbacks
        self.packet_callback: Optional[Callable] = None
        self.status_changed_callback: Optional[Callable] = None
        self.debug_print_callback: Optional[Callable] = None
        self.temperature_changed_callback: Optional[Callable] = None

    def connect(self) -> bool:
        """
        Connect to the Vallox unit via serial port

        Returns:
            True if connection successful
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1  # Non-blocking read with small timeout
            )
            self.full_init_done = False
            self.request_config()
            return True
        except Exception as e:
            if self._debug:
                print(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def request_config(self):
        """Request all configuration from the Vallox unit"""
        self._send_status_req()
        self._send_io08_req()
        self._send_fan_speed_req()
        self._send_default_fan_speed_req()
        self._send_rh_req()
        self._send_service_period_req()
        self._send_service_counter_req()
        self._send_heating_target_req()
        self._send_flags06_req()
        self._send_program_req()

        self.data['updated'] = time.monotonic()
        self.last_requested = time.monotonic()

    def loop(self):
        """
        Main loop - call this regularly to process incoming messages

        This should be called continuously to read and process messages from the bus.
        """
        # Read and decode all available messages
        while True:
            message = self._read_message()
            if message is None:
                break
            self._decode_message(message)

        # Periodic queries
        now = time.monotonic()
        if now - self.last_requested > vp.QUERY_INTERVAL:
            self.last_requested = now
            if self._is_status_init_done():
                self._send_io08_req()
                self._send_service_counter_req()

        # Retry loop
        if now - self.last_retry_loop > vp.RETRY_INTERVAL:
            self._retry_loop()

    # Properties (read-only)
    @property
    def updated(self) -> float:
        """Get timestamp of last update"""
        return self.data['updated']

    @temperature(unit="°C")
    def inside_temp(self) -> int:
        """Get inside temperature in Celsius"""
        return self.data['inside_temp'].value if self.data['inside_temp'].value is not None else 0

    @temperature(unit="°C")
    def outside_temp(self) -> int:
        """Get outside temperature in Celsius"""
        return self.data['outside_temp'].value if self.data['outside_temp'].value is not None else 0

    @temperature(unit="°C")
    def incoming_temp(self) -> int:
        """Get incoming air temperature in Celsius"""
        return self.data['incoming_temp'].value if self.data['incoming_temp'].value is not None else 0

    @temperature(unit="°C")
    def exhaust_temp(self) -> int:
        """Get exhaust air temperature in Celsius"""
        return self.data['exhaust_temp'].value if self.data['exhaust_temp'].value is not None else 0

    @property
    def is_on(self) -> bool:
        """Check if unit is powered on"""
        return self.data['is_on'].value or False

    @property
    def is_rh_mode(self) -> bool:
        """Check if RH (humidity) mode is active"""
        return self.data['is_rh_mode'].value or False

    @property
    def is_heating_mode(self) -> bool:
        """Check if heating mode is active"""
        return self.data['is_heating_mode'].value or False

    @property
    def is_summer_mode(self) -> bool:
        """Check if summer mode is active"""
        return self.data['is_summer_mode'].value or False

    @property
    def is_error_relay(self) -> bool:
        """Check if error relay is active"""
        return self.data['is_error_relay'].value or False

    @property
    def is_motor_in(self) -> bool:
        """Check if intake motor is running"""
        return self.data['is_motor_in'].value or False

    @property
    def is_front_heating(self) -> bool:
        """Check if front heating is active"""
        return self.data['is_front_heating'].value or False

    @property
    def is_motor_out(self) -> bool:
        """Check if exhaust motor is running"""
        return self.data['is_motor_out'].value or False

    @property
    def is_extra_func(self) -> bool:
        """Check if extra function is active"""
        return self.data['is_extra_func'].value or False

    @property
    def is_filter(self) -> bool:
        """Check if filter warning is active"""
        return self.data['is_filter'].value or False

    @property
    def is_heating(self) -> bool:
        """Check if heating is active"""
        return self.data['is_heating'].value or False

    @property
    def is_fault(self) -> bool:
        """Check if fault is present"""
        return self.data['is_fault'].value or False

    @property
    def is_service_needed(self) -> bool:
        """Check if service is needed"""
        return self.data['is_service_needed'].value or False

    @property
    def is_switch_active(self) -> bool:
        """Check if boost/fireplace switch is active"""
        return self.data['is_switch_active'].value or False

    @property
    def rh1(self) -> int:
        """Get RH sensor 1 value (%)"""
        if not self.data['rh1'].last_received:
            return vp.NOT_SET
        return self.data['rh1'].value if self.data['rh1'].value is not None else vp.NOT_SET

    @property
    def rh2(self) -> int:
        """Get RH sensor 2 value (%)"""
        if not self.data['rh2'].last_received:
            return vp.NOT_SET
        return self.data['rh2'].value if self.data['rh2'].value is not None else vp.NOT_SET

    @property
    def co2(self) -> int:
        """Get CO2 sensor value (ppm)"""
        if not self.data['co2'].last_received:
            return vp.NOT_SET
        return self.data['co2'].value if self.data['co2'].value is not None else vp.NOT_SET

    @property
    def switch_type(self) -> int:
        """Get switch type (0=fireplace, 1=boost, vp.NOT_SET=unknown)"""
        if not self.settings['is_boost_setting'].last_received:
            return vp.NOT_SET
        return 1 if self.settings['is_boost_setting'].value else 0

    @property
    def init_ok(self) -> bool:
        """Check if initialization is complete"""
        return self.full_init_done

    # Properties (read-write)
    @property
    def fan_speed(self) -> int:
        """Get current fan speed (1-8)"""
        return self.data['fan_speed'].value if self.data['fan_speed'].value is not None else vp.NOT_SET

    @fan_speed.setter
    def fan_speed(self, speed: int):
        """Set fan speed (1-8)"""
        if speed <=vp.VX_MAX_FAN_SPEED:
            self._set_variable(vp.VX_VARIABLE_FAN_SPEED, self._fan_speed_to_hex(speed))
            self.data['fan_speed'].value = speed
            self._call_status_changed('fan_speed')

    @property
    def default_fan_speed(self) -> int:
        """Get default fan speed (1-8)"""
        return self.data['default_fan_speed'].value if self.data['default_fan_speed'].value is not None else vp.NOT_SET

    @default_fan_speed.setter
    def default_fan_speed(self, speed: int):
        """Set default fan speed (1-8)"""
        if speed <=vp.VX_MAX_FAN_SPEED:
            self._set_variable(vp.VX_VARIABLE_DEFAULT_FAN_SPEED, self._fan_speed_to_hex(speed))
            self.data['default_fan_speed'].value = speed
            self._call_status_changed('default_fan_speed')

    @property
    def service_period(self) -> int:
        """Get service period in months"""
        return self.data['service_period'].value if self.data['service_period'].value is not None else vp.NOT_SET

    @service_period.setter
    def service_period(self, months: int):
        """Set service period in months"""
        if 0 <= months < 256:
            self._set_variable(vp.VX_VARIABLE_SERVICE_PERIOD, months)
            self.data['service_period'].value = months
            self._call_status_changed('service_period')

    @property
    def service_counter(self) -> int:
        """Get service counter in months"""
        return self.data['service_counter'].value if self.data['service_counter'].value is not None else vp.NOT_SET

    @service_counter.setter
    def service_counter(self, months: int):
        """Set service counter in months"""
        if 0 <= months < 256:
            self._set_variable(vp.VX_VARIABLE_SERVICE_COUNTER, months)
            self.data['service_counter'].value = months
            self._call_status_changed('service_counter')

    @property
    def heating_target(self) -> int:
        """Get heating target temperature in Celsius"""
        return self.data['heating_target'].value if self.data['heating_target'].value is not None else vp.NOT_SET

    @heating_target.setter
    def heating_target(self, celsius: int):
        """Set heating target temperature (10-27°C)"""
        if 10 <= celsius <= 27:
            hex_val = self._cel_to_ntc(celsius)
            self._set_variable(vp.VX_VARIABLE_HEATING_TARGET, hex_val)
            self.data['heating_target'].value = celsius
            self._call_status_changed('heating_target')

    @property
    def debug(self) -> bool:
        """Get debug mode status"""
        return self._debug

    @debug.setter
    def debug(self, value: bool):
        """Enable or disable debug mode"""
        self._debug = value

    # Action methods (previously setters without corresponding getters)
    def set_on(self):
        """Turn the unit on"""
        if self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                     self.data['status'].value |vp.VX_STATUS_FLAG_POWER):
            self.data['is_on'].value = True
            self._call_status_changed('is_on')

    def set_off(self):
        """Turn the unit off"""
        if self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                     self.data['status'].value & ~vp.VX_STATUS_FLAG_POWER):
            self.data['is_on'].value = False
            self._call_status_changed('is_on')

    def set_rh_mode_on(self):
        """Enable RH (humidity) mode"""
        if self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                     self.data['status'].value |vp.VX_STATUS_FLAG_RH):
            self.data['is_rh_mode'].value = True
            self._call_status_changed('is_rh_mode')

    def set_rh_mode_off(self):
        """Disable RH (humidity) mode"""
        if self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                     self.data['status'].value & ~vp.VX_STATUS_FLAG_RH):
            self.data['is_rh_mode'].value = False
            self._call_status_changed('is_rh_mode')

    def set_heating_mode_on(self):
        """Enable heating mode"""
        if self.data['status'].value &vp.VX_STATUS_FLAG_HEATING_MODE:
            self._debug_print("Heating mode is already on!")
            self._call_status_changed('is_heating_mode')
        elif self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                       self.data['status'].value | vp.VX_STATUS_FLAG_HEATING_MODE):
            self.data['is_heating_mode'].value = True
            self._call_status_changed('is_heating_mode')

    def set_heating_mode_off(self):
        """Disable heating mode"""
        if not (self.data['status'].value & vp.VX_STATUS_FLAG_HEATING_MODE):
            self._debug_print("Heating mode is already off!")
            self._call_status_changed('is_heating_mode')
        elif self._set_status_variable(vp.VX_VARIABLE_STATUS, 
                                       self.data['status'].value & ~vp.VX_STATUS_FLAG_HEATING_MODE):
            self.data['is_heating_mode'].value = False
            self._call_status_changed('is_heating_mode')

    def set_switch_on(self):
        """Activate boost/fireplace switch"""
        self._set_variable(vp.VX_VARIABLE_FLAGS_06, 
                          self.data['flags06'].value | vp.VX_06_FIREPLACE_FLAG_ACTIVATE)

    # Callback setters
    def set_packet_callback(self, callback: Callable):
        """Set callback for packet events"""
        self.packet_callback = callback

    def set_status_changed_callback(self, callback: Callable):
        """Set callback for status changes"""
        self.status_changed_callback = callback

    def set_debug_print_callback(self, callback: Callable):
        """Set callback for debug messages"""
        self.debug_print_callback = callback

    def set_temperature_changed_callback(self, callback: Callable):
        """Set callback for temperature changes"""
        self.temperature_changed_callback = callback

    # Private methods - Serial communication
    def _read_message(self) -> Optional[bytes]:
        """
        Read one complete message from serial port

        Returns:
            Message bytes if a valid message was read, None otherwise
        """
        if not self.serial or not self.serial.is_open:
            return None

        if self.serial.in_waiting < vp.VX_MSG_LENGTH:
            return None

        # Read first byte
        first_byte = self.serial.read(1)
        if len(first_byte) == 0 or first_byte[0] != vp.VX_MSG_DOMAIN:
            return None

        # Read next two bytes
        sender = self.serial.read(1)
        receiver = self.serial.read(1)

        if len(sender) == 0 or len(receiver) == 0:
            return None

        sender_byte = sender[0]
        receiver_byte = receiver[0]

        # Filter messages
        valid_sender = sender_byte in [vp.VX_MSG_MAINBOARD_1, vp.VX_MSG_THIS_PANEL, vp.VX_MSG_PANEL_1]
        valid_receiver = receiver_byte in [vp.VX_MSG_PANELS, vp.VX_MSG_THIS_PANEL, vp.VX_MSG_PANEL_1, 
                                          vp.VX_MSG_MAINBOARD_1, vp.VX_MSG_MAINBOARDS]

        if not (valid_sender and valid_receiver):
            return None

        # Read rest of message
        rest = self.serial.read(vp.VX_MSG_LENGTH - 3)
        if len(rest) != vp.VX_MSG_LENGTH - 3:
            return None

        message = first_byte + sender + receiver + rest

        if self._debug and self.packet_callback:
            self.packet_callback(message, "packetRecv")

        return message

    def _decode_message(self, message: bytes):
        """Decode received message and update internal state"""
        if not self._validate_checksum(message):
            return

        variable = message[3]
        value = message[4]
        now = time.monotonic()

        # Temperature variables
        if variable == vp.VX_VARIABLE_T_OUTSIDE:
            self._check_status_change('outside_temp', self._ntc_to_cel(value))
        elif variable == vp.VX_VARIABLE_T_EXHAUST:
            self._check_status_change('exhaust_temp', self._ntc_to_cel(value))
        elif variable == vp.VX_VARIABLE_T_INSIDE:
            self._check_status_change('inside_temp', self._ntc_to_cel(value))
        elif variable == vp.VX_VARIABLE_T_INCOMING:
            self._check_status_change('incoming_temp', self._ntc_to_cel(value))

        # RH variables
        elif variable == vp.VX_VARIABLE_RH1:
            self._check_status_change('rh1', self._hex_to_rh(value))
        elif variable == vp.VX_VARIABLE_RH2:
            self._check_status_change('rh2', self._hex_to_rh(value), now)

        # CO2 variables
        elif variable == vp.VX_VARIABLE_CO2_HI:
            self.data['co2_hi'].last_received = now
            self.data['co2_hi'].value = value
            if now - self.data['co2_lo'].last_received < vp.CO2_LIFE_TIME_MS / 1000:
                self._handle_co2_total_value(self.data['co2_hi'].value, 
                                            self.data['co2_lo'].value)
        elif variable == vp.VX_VARIABLE_CO2_LO:
            self.data['co2_lo'].last_received = now
            self.data['co2_lo'].value = value
            if now - self.data['co2_hi'].last_received < vp.CO2_LIFE_TIME_MS / 1000:
                self._handle_co2_total_value(self.data['co2_hi'].value, 
                                            self.data['co2_lo'].value)

        # Configuration variables
        elif variable == vp.VX_VARIABLE_FAN_SPEED:
            self.data['fan_speed'].last_received = now
            self._check_status_change('fan_speed', 
                                     self._hex_to_fan_speed(value))
        elif variable == vp.VX_VARIABLE_DEFAULT_FAN_SPEED:
            self.data['default_fan_speed'].last_received = now
            self._check_status_change('default_fan_speed', 
                                     self._hex_to_fan_speed(value))
        elif variable == vp.VX_VARIABLE_STATUS:
            self._decode_status(value)
        elif variable == vp.VX_VARIABLE_IO_08:
            self._decode_variable08(value)
        elif variable == vp.VX_VARIABLE_FLAGS_06:
            self._decode_flags06(value)
        elif variable == vp.VX_VARIABLE_SERVICE_PERIOD:
            self.data['service_period'].last_received = now
            self._check_status_change('service_period', value)
        elif variable == vp.VX_VARIABLE_SERVICE_COUNTER:
            self.data['service_counter'].last_received = now
            self._check_status_change('service_counter', value)
        elif variable == vp.VX_VARIABLE_HEATING_TARGET:
            self.data['heating_target'].last_received = now
            self._check_status_change('heating_target', 
                                     self._ntc_to_cel(value))
        elif variable == vp.VX_VARIABLE_PROGRAM:
            self._decode_program(value)

        # Check if initialization is complete
        if not self.full_init_done:
            self.full_init_done = self._is_status_init_done()
            if self.full_init_done:
                for k, _ in self.data.items():
                    self._call_status_changed(k)

    def _decode_status(self, status: int):
        """Decode status byte"""
        now = time.monotonic()

        self.data['is_on'].last_received = now
        self.data['is_rh_mode'].last_received = now
        self.data['is_heating_mode'].last_received = now
        self.data['is_filter'].last_received = now
        self.data['is_heating'].last_received = now
        self.data['is_fault'].last_received = now
        self.data['is_service_needed'].last_received = now

        self.data['status'].value = status
        self.data['status'].last_received = now

        self._check_status_change('is_on', 
                                 (status & vp.VX_STATUS_FLAG_POWER) != 0)
        self._check_status_change('is_rh_mode', 
                                 (status & vp.VX_STATUS_FLAG_RH) != 0)
        self._check_status_change('is_heating_mode', 
                                 (status & vp.VX_STATUS_FLAG_HEATING_MODE) != 0)
        self._check_status_change('is_filter', 
                                 (status & vp.VX_STATUS_FLAG_FILTER) != 0)
        self._check_status_change('is_heating', 
                                 (status & vp.VX_STATUS_FLAG_HEATING) != 0)
        self._check_status_change('is_fault', 
                                 (status & vp.VX_STATUS_FLAG_FAULT) != 0)
        self._check_status_change('is_service_needed', 
                                 (status & vp.VX_STATUS_FLAG_SERVICE) != 0)

        self.status_mutex = False

    def _decode_variable08(self, variable08: int):
        """Decode variable 08 byte"""
        now = time.monotonic()

        self.data['is_summer_mode'].last_received = now
        self.data['is_error_relay'].last_received = now
        self.data['is_motor_in'].last_received = now
        self.data['is_front_heating'].last_received = now
        self.data['is_motor_out'].last_received = now
        self.data['is_extra_func'].last_received = now

        self.data['variable08'].value = variable08
        self.data['variable08'].last_received = now

        self._check_status_change('is_summer_mode', 
                                 (variable08 & vp.VX_08_FLAG_SUMMER_MODE) != 0)
        self._check_status_change('is_error_relay', 
                                 (variable08 & vp.VX_08_FLAG_ERROR_RELAY) != 0)
        self._check_status_change('is_motor_in', 
                                 (variable08 & vp.VX_08_FLAG_MOTOR_IN) != 0)
        self._check_status_change('is_front_heating', 
                                 (variable08 & vp.VX_08_FLAG_FRONT_HEATING) != 0)
        self._check_status_change('is_motor_out', 
                                 (variable08 & vp.VX_08_FLAG_MOTOR_OUT) != 0)
        self._check_status_change('is_extra_func', 
                                 (variable08 & vp.VX_08_FLAG_EXTRA_FUNC) != 0)

    def _decode_flags06(self, flags06: int):
        """Decode flags 06 byte"""
        now = time.monotonic()

        self.data['is_switch_active'].last_received = now
        self.data['flags06'].value = flags06
        self.data['flags06'].last_received = now

        self._check_status_change('is_switch_active', 
                                 (flags06 & vp.VX_06_FIREPLACE_FLAG_IS_ACTIVE) != 0)

    def _decode_program(self, program: int):
        """Decode program byte"""
        should_inform = not self.settings['is_boost_setting'].last_received

        now = time.monotonic()
        self.settings['is_boost_setting'].last_received = now
        self.settings['program'].value = program
        self.settings['program'].last_received = now

        old_value = self.settings['is_boost_setting'].value
        new_value = (program & vp.VX_PROGRAM_SWITCH_TYPE) != 0

        if old_value != new_value:
            self.settings['is_boost_setting'].value = new_value
            self._call_status_changed('is_boost_setting')
        elif should_inform:
            self._call_status_changed('is_boost_setting')

    def _set_variable(self, variable: int, value: int, target: int = vp.VX_MSG_MAINBOARDS):
        """Send variable set command"""
        if not self.serial or not self.serial.is_open:
            return

        # Send to mainboards/specific target
        message = bytearray([
            vp.VX_MSG_DOMAIN,
            vp.VX_MSG_THIS_PANEL,
            target,
            variable,
            value,
            0
        ])
        message[5] = self._calculate_checksum(message)

        self.serial.write(message)

        if self._debug and self.packet_callback:
            self.packet_callback(bytes(message), "packetSent")

        # Also send to panels
        message[1] = vp.VX_MSG_MAINBOARD_1
        message[2] = vp.VX_MSG_PANELS
        message[5] = self._calculate_checksum(message)

        self.serial.write(message)

    def _set_status_variable(self, variable: int, value: int) -> bool:
        """Set status variable with mutex protection"""
        if not self.status_mutex:
            self.status_mutex = True
            self._set_variable(variable, value, vp.VX_MSG_MAINBOARD_1)
            self.last_retry_loop = time.monotonic()
            return True
        return False

    def _request_variable(self, variable: int):
        """Request variable value from Vallox"""
        if not self.serial or not self.serial.is_open:
            return

        message = bytearray([
            vp.VX_MSG_DOMAIN,
            vp.VX_MSG_THIS_PANEL,
            vp.VX_MSG_MAINBOARD_1,
            vp.VX_MSG_POLL_BYTE,
            variable,
            0
        ])
        message[5] = self._calculate_checksum(message)

        if self._debug and self.packet_callback:
            self.packet_callback(bytes(message), "packetSent")

        self.serial.write(message)
        time.sleep(0.1)  # Small delay after request

    # Request methods
    def _send_status_req(self):
        self._request_variable(vp.VX_VARIABLE_STATUS)

    def _send_io08_req(self):
        self._request_variable(vp.VX_VARIABLE_IO_08)

    def _send_flags06_req(self):
        self._request_variable(vp.VX_VARIABLE_FLAGS_06)

    def _send_fan_speed_req(self):
        self._request_variable(vp.VX_VARIABLE_FAN_SPEED)

    def _send_default_fan_speed_req(self):
        self._request_variable(vp.VX_VARIABLE_DEFAULT_FAN_SPEED)

    def _send_service_period_req(self):
        self._request_variable(vp.VX_VARIABLE_SERVICE_PERIOD)

    def _send_service_counter_req(self):
        self._request_variable(vp.VX_VARIABLE_SERVICE_COUNTER)

    def _send_heating_target_req(self):
        self._request_variable(vp.VX_VARIABLE_HEATING_TARGET)

    def _send_rh_req(self):
        self._request_variable(vp.VX_VARIABLE_RH1)

    def _send_program_req(self):
        self._request_variable(vp.VX_VARIABLE_PROGRAM)

    # Conversion methods
    @staticmethod
    def _fan_speed_to_hex(fan: int) -> int:
        """Convert fan speed (1-8) to hex value"""
        if 1 <= fan <= 8:
            return vp.VX_FAN_SPEEDS[fan - 1]
        return vp.VX_FAN_SPEED_1

    @staticmethod
    def _hex_to_fan_speed(hex_val: int) -> int:
        """Convert hex value to fan speed (1-8)"""
        try:
            return vp.VX_FAN_SPEEDS.index(hex_val) + 1
        except ValueError:
            return vp.NOT_SET

    @staticmethod
    def _ntc_to_cel(ntc: int) -> int:
        """Convert NTC value to Celsius"""
        if 0 <= ntc < len(vp.VX_TEMPS):
            return vp.VX_TEMPS[ntc]
        return vp.NOT_SET

    @staticmethod
    def _cel_to_ntc(cel: int) -> int:
        """Convert Celsius to NTC value"""
        try:
            return vp.VX_TEMPS.index(cel)
        except ValueError:
            return 0x83  # Default to 10°C

    @staticmethod
    def _hex_to_rh(hex_val: int) -> int:
        """Convert hex value to RH percentage"""
        if hex_val >= 51:
            return int((hex_val - 51) / 2.04)
        return vp.NOT_SET

    # Helper methods
    @staticmethod
    def _calculate_checksum(message: bytearray) -> int:
        """Calculate message checksum"""
        return sum(message[:5]) & 0xFF

    def _validate_checksum(self, message: bytes) -> bool:
        """Validate message checksum"""
        calculated = self._calculate_checksum(bytearray(message[:5]))
        received = message[5]

        if calculated != received:
            self._debug_print("Checksum comparison failed!")
            return False
        return True

    def _check_status_change(self, name: str, new_value: Any):
        """Check and update status field if changed"""
        data_field = self.data[name]
        if data_field.value != new_value:
            data_field.value = new_value
            self.data['updated'] = time.monotonic()
            if self.full_init_done:
                self.on_property_changed(name, new_value)
                self._call_status_changed(name)

    def _check_value_change(self, name: str, new_value: Any):
        """Check and update value field if changed (for temperatures, CO2, RH)"""
        data_field: ValueWithTimestamp= self.data[name]
        data_field.last_received = time
        if data_field.value != new_value:
            data_field.value = new_value
            self.data['updated'] = time
            if self._is_temperature_init_done():
                self._call_temperature_changed()

    def _handle_co2_total_value(self, hi: int, lo: int):
        """Construct CO2 value from high and low bytes"""
        total = lo + (hi << 8)
        self._check_status_change('co2', total)

    def _is_temperature_init_done(self) -> bool:
        """Check if all temperatures have been received"""
        return (self.data['outside_temp'].last_received and
                self.data['inside_temp'].last_received and
                self.data['exhaust_temp'].last_received and
                self.data['incoming_temp'].last_received)

    def _is_status_init_done(self) -> bool:
        """Check if all status values have been received"""
        return (self.data['is_on'].last_received and
                self.data['is_rh_mode'].last_received and
                self.data['is_heating_mode'].last_received and
                self.data['variable08'].last_received and
                self.data['is_filter'].last_received and
                self.data['is_heating'].last_received and
                self.data['is_fault'].last_received and
                self.data['is_service_needed'].last_received and
                self.data['fan_speed'].last_received and
                self.data['default_fan_speed'].last_received and
                self.data['service_period'].last_received and
                self.data['service_counter'].last_received and
                self.data['heating_target'].last_received)

    def _retry_loop(self):
        """Retry missing requests and clear mutex"""
        self._send_missing_requests()
        self.status_mutex = False
        self.last_retry_loop = time.monotonic()

    def _send_missing_requests(self):
        """Send requests for missing data"""
        if not self.data['is_on'].last_received:
            self._send_status_req()
        if not self.data['variable08'].last_received:
            self._send_io08_req()
        if not self.data['fan_speed'].last_received:
            self._send_fan_speed_req()
        if not self.data['default_fan_speed'].last_received:
            self._send_default_fan_speed_req()
        if not self.data['service_period'].last_received:
            self._send_service_period_req()
        if not self.data['service_counter'].last_received:
            self._send_service_counter_req()
        if not self.data['heating_target'].last_received:
            self._send_heating_target_req()

    def _call_status_changed(self, name: str):
        """Call status changed callback if set"""
        if self.status_changed_callback:
            self.status_changed_callback(name)

    def _call_temperature_changed(self):
        """Call temperature changed callback if set"""
        if self.temperature_changed_callback:
            self.temperature_changed_callback()

    def _debug_print(self, message: str):
        """Print debug message"""
        if self._debug:
            if self.debug_print_callback:
                self.debug_print_callback(message)
            else:
                print(f"[DEBUG] {message}")


async def poll_device(state: LoopState, device: Vallox):
    """Poll data from the vallox device."""
    print("Starting polling task...")

    if device.connect():
        print("Connected to Vallox device.")

    while not state.stop.is_set():
        device.loop()
        await asyncio.sleep(0.1)
    print("Polling task stopped.")

def create_devices():
    """Create and return a list of vallox devices and their polling functions."""
    port = env.get("VALLOX_SERIAL_PORT", "/dev/ttyUSB0")
    debug = env.get("VALLOX_DEBUG", "false").lower() == "true"
    return [(Vallox(root_topic="ventilation",
                    port=port,
                    baudrate=9600,
                    debug=debug), poll_device)]



