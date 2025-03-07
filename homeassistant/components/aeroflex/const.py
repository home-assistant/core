"""Constants for the Aeroflex Adjustable Bed integration."""

from enum import IntEnum

DOMAIN = "aeroflex"
CONF_DEVICE_ADDRESS = "address"
CONF_DEVICE_NAME = "name"

# BLE Service UUID for Aeroflex devices
SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

MIN_ANGLE = 0
MAX_HEAD_ANGLE = 60  # degrees
MAX_FEET_ANGLE = 30  # degrees
STEP_DURATION = 0.15  # seconds
HEAD_MOTION_TIME = 20  # seconds
FEET_MOTION_TIME = 15  # seconds


class BedCommand(IntEnum):
    """Commands for controlling the bed."""

    HEAD_UP = 0x34
    FEET_UP = 0x36
    HEAD_DOWN = 0x37
    BOTH_UP = 0x38
    BOTH_DOWN = 0x39
    FEET_DOWN = 0x41
