"""
Vallox Digit SE Communication Protocol Constants
"""

# Message structure
VX_MSG_LENGTH = 6
VX_MSG_DOMAIN = 0x01
VX_MSG_POLL_BYTE = 0x00

# Senders and receivers
VX_MSG_MAINBOARD_1 = 0x11
VX_MSG_MAINBOARDS = 0x10
VX_MSG_PANEL_1 = 0x21
VX_MSG_THIS_PANEL = 0x22
VX_MSG_PANELS = 0x20

# Variables
VX_VARIABLE_STATUS = 0xA3
VX_VARIABLE_FAN_SPEED = 0x29
VX_VARIABLE_DEFAULT_FAN_SPEED = 0xA9
VX_VARIABLE_RH1 = 0x2F
VX_VARIABLE_RH2 = 0x30
VX_VARIABLE_SERVICE_PERIOD = 0xA6
VX_VARIABLE_SERVICE_COUNTER = 0xAB
VX_VARIABLE_T_OUTSIDE = 0x32
VX_VARIABLE_T_INSIDE = 0x34
VX_VARIABLE_T_EXHAUST = 0x33
VX_VARIABLE_T_INCOMING = 0x35
VX_VARIABLE_IO_08 = 0x08
VX_VARIABLE_HEATING_TARGET = 0xA4
VX_VARIABLE_FAULT_CODE = 0x36
VX_VARIABLE_FLAGS_06 = 0x71
VX_VARIABLE_HEATING_STATUS = 0x07
VX_VARIABLE_PROGRAM = 0xAA
VX_VARIABLE_CO2_HI = 0x2B
VX_VARIABLE_CO2_LO = 0x2C

# Status flags (variable A3)
VX_STATUS_FLAG_POWER = 0x01
VX_STATUS_FLAG_CO2 = 0x02
VX_STATUS_FLAG_RH = 0x04
VX_STATUS_FLAG_HEATING_MODE = 0x08
VX_STATUS_FLAG_FILTER = 0x10
VX_STATUS_FLAG_HEATING = 0x20
VX_STATUS_FLAG_FAULT = 0x40
VX_STATUS_FLAG_SERVICE = 0x80

# Flags of variable 08
VX_08_FLAG_SUMMER_MODE = 0x02
VX_08_FLAG_ERROR_RELAY = 0x04
VX_08_FLAG_MOTOR_IN = 0x08
VX_08_FLAG_FRONT_HEATING = 0x10
VX_08_FLAG_MOTOR_OUT = 0x20
VX_08_FLAG_EXTRA_FUNC = 0x40

# Flags of variable 06 (boost/fireplace)
VX_06_FIREPLACE_FLAG_ACTIVATE = 0x20
VX_06_FIREPLACE_FLAG_IS_ACTIVE = 0x40

# Program variable flags
VX_PROGRAM_SWITCH_TYPE = 0x20

# Fan speeds
VX_FAN_SPEED_1 = 0x01
VX_FAN_SPEED_2 = 0x03
VX_FAN_SPEED_3 = 0x07
VX_FAN_SPEED_4 = 0x0F
VX_FAN_SPEED_5 = 0x1F
VX_FAN_SPEED_6 = 0x3F
VX_FAN_SPEED_7 = 0x7F
VX_FAN_SPEED_8 = 0xFF
VX_MIN_FAN_SPEED = 1
VX_MAX_FAN_SPEED = 8

# Fan speed conversion table
VX_FAN_SPEEDS = [
    VX_FAN_SPEED_1,
    VX_FAN_SPEED_2,
    VX_FAN_SPEED_3,
    VX_FAN_SPEED_4,
    VX_FAN_SPEED_5,
    VX_FAN_SPEED_6,
    VX_FAN_SPEED_7,
    VX_FAN_SPEED_8
]

# NTC temperature conversion table
VX_TEMPS = [
    -74, -70, -66, -62, -59, -56, -54, -52, -50, -48,  # 0x00 - 0x09
    -47, -46, -44, -43, -42, -41, -40, -39, -38, -37,  # 0x0a - 0x13
    -36, -35, -34, -33, -33, -32, -31, -30, -30, -29,  # 0x14 - 0x1d
    -28, -28, -27, -27, -26, -25, -25, -24, -24, -23,  # 0x1e - 0x27
    -23, -22, -22, -21, -21, -20, -20, -19, -19, -19,  # 0x28 - 0x31
    -18, -18, -17, -17, -16, -16, -16, -15, -15, -14,  # 0x32 - 0x3b
    -14, -14, -13, -13, -12, -12, -12, -11, -11, -11,  # 0x3c - 0x45
    -10, -10, -9, -9, -9, -8, -8, -8, -7, -7,           # 0x46 - 0x4f
    -7, -6, -6, -6, -5, -5, -5, -4, -4, -4,             # 0x50 - 0x59
    -3, -3, -3, -2, -2, -2, -1, -1, -1, -1,             # 0x5a - 0x63
    0, 0, 0, 1, 1, 1, 2, 2, 2, 3,                       # 0x64 - 0x6d
    3, 3, 4, 4, 4, 5, 5, 5, 5, 6,                       # 0x6e - 0x77
    6, 6, 7, 7, 7, 8, 8, 8, 9, 9,                       # 0x78 - 0x81
    9, 10, 10, 10, 11, 11, 11, 12, 12, 12,             # 0x82 - 0x8b
    13, 13, 13, 14, 14, 14, 15, 15, 15, 16,            # 0x8c - 0x95
    16, 16, 17, 17, 18, 18, 18, 19, 19, 19,            # 0x96 - 0x9f
    20, 20, 21, 21, 21, 22, 22, 22, 23, 23,            # 0xa0 - 0xa9
    24, 24, 24, 25, 25, 26, 26, 27, 27, 27,            # 0xaa - 0xb3
    28, 28, 29, 29, 30, 30, 31, 31, 32, 32,            # 0xb4 - 0xbd
    33, 33, 34, 34, 35, 35, 36, 36, 37, 37,            # 0xbe - 0xc7
    38, 38, 39, 40, 40, 41, 41, 42, 43, 43,            # 0xc8 - 0xd1
    44, 45, 45, 46, 47, 48, 48, 49, 50, 51,            # 0xd2 - 0xdb
    52, 53, 53, 54, 55, 56, 57, 59, 60, 61,            # 0xdc - 0xe5
    62, 63, 65, 66, 68, 69, 71, 73, 75, 77,            # 0xe6 - 0xef
    79, 81, 82, 86, 90, 93, 97, 100, 100, 100,         # 0xf0 - 0xf9
    100, 100, 100, 100, 100, 100                       # 0xfa - 0xff
]

# Special values
NOT_SET = -999
QUERY_INTERVAL = 300  # seconds (5 minutes)
RETRY_INTERVAL = 5    # seconds
CO2_LIFE_TIME_MS = 2000  # milliseconds
