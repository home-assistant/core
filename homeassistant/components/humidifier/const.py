"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum
from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

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

DEFAULT_MIN_HUMIDITY = 0
DEFAULT_MAX_HUMIDITY = 100

DOMAIN = "humidifier"

# DEVICE_CLASS_* below are deprecated as of 2021.12
# use the HumidifierDeviceClass enum instead.
_DEPRECATED_DEVICE_CLASS_HUMIDIFIER = DeprecatedConstant(
    "humidifier", "HumidifierDeviceClass.HUMIDIFIER", "2025.1"
)
_DEPRECATED_DEVICE_CLASS_DEHUMIDIFIER = DeprecatedConstant(
    "dehumidifier", "HumidifierDeviceClass.DEHUMIDIFIER", "2025.1"
)

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_HUMIDITY = "set_humidity"


class HumidifierEntityFeature(IntFlag):
    """Supported features of the alarm control panel entity."""

    MODES = 1


# The SUPPORT_MODES constant is deprecated as of Home Assistant 2022.5.
# Please use the HumidifierEntityFeature enum instead.
_DEPRECATED_SUPPORT_MODES = DeprecatedConstantEnum(
    HumidifierEntityFeature.MODES, "2025.1"
)

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
