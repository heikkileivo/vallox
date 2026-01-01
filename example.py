#!/usr/bin/env python3
"""
Example script for using the Vallox serial communication library

This demonstrates basic usage of the Vallox library to read status
and control a Vallox air conditioning unit via serial port.
"""

import time
from vallox import Vallox


def packet_debug(packet, direction):
    """Callback for packet debug"""
    hex_str = ' '.join(f'{b:02x}' for b in packet)
    print(f"[{direction}] {hex_str}")


def main():
    """Main function"""
    global vx
    
    # Configuration
    SERIAL_PORT = "/dev/ttyUSB0"  # Change this to your serial port
    DEBUG = True  # Set to False to disable debug output
    
    print("Vallox Serial Communication Example")
    print("=" * 50)
    
    # Create Vallox instance
    vx = Vallox(port=SERIAL_PORT, baudrate=9600, debug=DEBUG)
    
    def status_changed():
        """Callback when status changes"""
        print("\n=== Status Changed ===")
        print(f"Power: {'ON' if vx.is_on() else 'OFF'}")
        print(f"Heating Mode: {'ON' if vx.is_heating_mode() else 'OFF'}")
        print(f"Fan Speed: {vx.get_fan_speed()}")
        print(f"Default Fan Speed: {vx.get_default_fan_speed()}")
        print(f"Heating Target: {vx.get_heating_target()}°C")
        print(f"Service Counter: {vx.get_service_counter()} months")
        print(f"Filter Warning: {'YES' if vx.is_filter() else 'NO'}")
        print(f"Fault: {'YES' if vx.is_fault() else 'NO'}")

    def debug_print(message):
        """Callback for debug messages"""
        print(f"[DEBUG] {message}")

    def temperature_changed():
        """Callback when temperature values change"""
        print("\n=== Temperature Update ===")
        print(f"Inside: {vx.get_inside_temp()}°C")
        print(f"Outside: {vx.get_outside_temp()}°C")
        print(f"Incoming: {vx.get_incoming_temp()}°C")
        print(f"Exhaust: {vx.get_exhaust_temp()}°C")
        
        rh1 = vx.get_rh1()
        rh2 = vx.get_rh2()
        co2 = vx.get_co2()
    
        if rh1 != -999:
            print(f"RH1: {rh1}%")
        if rh2 != -999:
            print(f"RH2: {rh2}%")
        if co2 != -999:
            print(f"CO2: {co2} ppm")

    # Set up callbacks
    vx.set_status_changed_callback(status_changed)
    vx.set_temperature_changed_callback(temperature_changed)
    vx.set_debug_print_callback(debug_print)
    
    if DEBUG:
        vx.set_packet_callback(packet_debug)
    
    # Connect to the unit
    print(f"\nConnecting to {SERIAL_PORT}...")
    if not vx.connect():
        print("Failed to connect!")
        return
    
    print("Connected successfully!")
    print("Waiting for initialization...\n")
    
    try:
        # Main loop
        while True:
            vx.loop()
            
            # Check if initialization is complete
            if vx.is_init_ok() and not hasattr(main, 'init_printed'):
                print("\n=== Initialization Complete ===")
                main.init_printed = True
            
            # Small sleep to prevent CPU hogging
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        vx.disconnect()
        print("Disconnected.")


def example_control():
    """
    Example function showing how to control the Vallox unit
    
    Note: This is not called by default. You can call these methods
    from the main loop or create a separate control interface.
    """
    # Turn on the unit
    vx.set_on()
    
    # Set fan speed to level 3
    vx.set_fan_speed(3)
    
    # Enable heating mode
    vx.set_heating_mode_on()
    
    # Set heating target to 22°C
    vx.set_heating_target(22)
    
    # Activate boost/fireplace switch
    vx.set_switch_on()
    
    # Turn off heating mode
    vx.set_heating_mode_off()


if __name__ == "__main__":
    main()
