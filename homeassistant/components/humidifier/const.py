"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum

MODE_NORMAL = "normal"
MODE_ECO = "eco"
MODE_AWAY = "away"
MODE_BOOST = "boost"
MODE_COMFORT = "comfort"
MODE_HOME = "home"
MODE_SLEEP = "sleep"
MODE_AUTO = "auto"
MODE_BABY = "baby"


class HumidifierAction(StrEnum):
    """Actions for humidifier devices."""

    HUMIDIFYING = "humidifying"
    DRYING = "drying"
    IDLE = "idle"
    OFF = "off"


ATTR_ACTION = "action"
ATTR_AVAILABLE_MODES = "available_modes"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_TARGET_HUMIDITY_STEP = "target_humidity_step"

DEFAULT_MIN_HUMIDITY = 0
DEFAULT_MAX_HUMIDITY = 100

DOMAIN = "humidifier"

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_HUMIDITY = "set_humidity"


class HumidifierEntityCapabilityAttribute(StrEnum):
    """Capability attributes for humidifier entities."""

    MIN_HUMIDITY = "min_humidity"
    MAX_HUMIDITY = "max_humidity"
    TARGET_HUMIDITY_STEP = "target_humidity_step"
    AVAILABLE_MODES = "available_modes"


class HumidifierEntityStateAttribute(StrEnum):
    """State attributes for humidifier entities."""

    ACTION = "action"
    CURRENT_HUMIDITY = "current_humidity"
    HUMIDITY = "humidity"
    MODE = "mode"


class HumidifierEntityFeature(IntFlag):
    """Supported features of the humidifier entity."""

    MODES = 1
