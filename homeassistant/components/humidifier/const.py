"""Provides the constants needed for component."""
from enum import IntEnum

MODE_NORMAL = "normal"
MODE_ECO = "eco"
MODE_AWAY = "away"
MODE_BOOST = "boost"
MODE_COMFORT = "comfort"
MODE_HOME = "home"
MODE_SLEEP = "sleep"
MODE_AUTO = "auto"
MODE_BABY = "baby"

# This are support current states of humidifier
CURRENT_HUMIDIFIER_OFF = "off"
CURRENT_HUMIDIFIER_HUMIDIFY = "humidifying"
CURRENT_HUMIDIFIER_DEHUMIDIFY = "dehumidifying"
CURRENT_HUMIDIFIER_IDLE = "idle"

# A list of possible humidifier actions.
CURRENT_HUMIDIFIER_ACTIONS = [
    CURRENT_HUMIDIFIER_OFF,
    CURRENT_HUMIDIFIER_HUMIDIFY,
    CURRENT_HUMIDIFIER_DEHUMIDIFY,
    CURRENT_HUMIDIFIER_IDLE,
]

ATTR_AVAILABLE_MODES = "available_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_HUMIDIFIER_ACTION = "humidifier_action"

DEFAULT_MIN_HUMIDITY = 0
DEFAULT_MAX_HUMIDITY = 100

DOMAIN = "humidifier"

# DEVICE_CLASS_* below are deprecated as of 2021.12
# use the HumidifierDeviceClass enum instead.
DEVICE_CLASS_HUMIDIFIER = "humidifier"
DEVICE_CLASS_DEHUMIDIFIER = "dehumidifier"

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_HUMIDITY = "set_humidity"


class HumidifierEntityFeature(IntEnum):
    """Supported features of the alarm control panel entity."""

    MODES = 1


# The SUPPORT_MODES constant is deprecated as of Home Assistant 2022.5.
# Please use the HumidifierEntityFeature enum instead.
SUPPORT_MODES = 1
