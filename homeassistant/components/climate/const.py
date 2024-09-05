"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum
from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)


class HVACMode(StrEnum):
    """HVAC mode for climate devices."""

    # All activity disabled / Device is off/standby
    OFF = "off"

    # Heating
    HEAT = "heat"

    # Cooling
    COOL = "cool"

    # The device supports heating/cooling to a range
    HEAT_COOL = "heat_cool"

    # The temperature is set based on a schedule, learned behavior, AI or some
    # other related mechanism. User is not able to adjust the temperature
    AUTO = "auto"

    # Device is in Dry/Humidity mode
    DRY = "dry"

    # Only the fan is on, not fan and another mode like cool
    FAN_ONLY = "fan_only"


# These HVAC_MODE_* constants are deprecated as of Home Assistant 2022.5.
# Please use the HVACMode enum instead.
_DEPRECATED_HVAC_MODE_OFF = DeprecatedConstantEnum(HVACMode.OFF, "2025.1")
_DEPRECATED_HVAC_MODE_HEAT = DeprecatedConstantEnum(HVACMode.HEAT, "2025.1")
_DEPRECATED_HVAC_MODE_COOL = DeprecatedConstantEnum(HVACMode.COOL, "2025.1")
_DEPRECATED_HVAC_MODE_HEAT_COOL = DeprecatedConstantEnum(HVACMode.HEAT_COOL, "2025.1")
_DEPRECATED_HVAC_MODE_AUTO = DeprecatedConstantEnum(HVACMode.AUTO, "2025.1")
_DEPRECATED_HVAC_MODE_DRY = DeprecatedConstantEnum(HVACMode.DRY, "2025.1")
_DEPRECATED_HVAC_MODE_FAN_ONLY = DeprecatedConstantEnum(HVACMode.FAN_ONLY, "2025.1")
HVAC_MODES = [cls.value for cls in HVACMode]


class PresetMode(StrEnum):
    """Preset mode for climate devices."""

    NONE = "none"
    ECO = "eco"
    AWAY = "away"
    BOOST = "boost"
    COMFORT = "comfort"
    HOME = "home"
    SLEEP = "sleep"
    ACTIVITY = "activity"


# These PRESET_* constants are deprecated as of Home Assistant 2024.10.
# Please use the PresetMode enum instead.
_DEPRECATED_PRESET_NONE = DeprecatedConstantEnum(PresetMode.NONE, "2025.10")
_DEPRECATED_PRESET_ECO = DeprecatedConstantEnum(PresetMode.ECO, "2025.10")
_DEPRECATED_PRESET_AWAY = DeprecatedConstantEnum(PresetMode.AWAY, "2025.10")
_DEPRECATED_PRESET_BOOST = DeprecatedConstantEnum(PresetMode.BOOST, "2025.10")
_DEPRECATED_PRESET_COMFORT = DeprecatedConstantEnum(PresetMode.COMFORT, "2025.10")
_DEPRECATED_PRESET_HOME = DeprecatedConstantEnum(PresetMode.HOME, "2025.10")
_DEPRECATED_PRESET_SLEEP = DeprecatedConstantEnum(PresetMode.SLEEP, "2025.10")
_DEPRECATED_PRESET_ACTIVITY = DeprecatedConstantEnum(PresetMode.ACTIVITY, "2025.10")
PRESET_MODES = [cls.value for cls in PresetMode]


class FanMode(StrEnum):
    """Fan mode for climate devices."""

    ON = "on"
    OFF = "off"
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    TOP = "top"
    MIDDLE = "middle"
    FOCUS = "focus"
    DIFFUSE = "diffuse"


# These FAN_* constants are deprecated as of Home Assistant 2024.10.
# Please use the FanMode enum instead.
_DEPRECATED_FAN_ON = DeprecatedConstantEnum(FanMode.ON, "2025.10")
_DEPRECATED_FAN_OFF = DeprecatedConstantEnum(FanMode.OFF, "2025.10")
_DEPRECATED_FAN_AUTO = DeprecatedConstantEnum(FanMode.AUTO, "2025.10")
_DEPRECATED_FAN_LOW = DeprecatedConstantEnum(FanMode.LOW, "2025.10")
_DEPRECATED_FAN_MEDIUM = DeprecatedConstantEnum(FanMode.MEDIUM, "2025.10")
_DEPRECATED_FAN_HIGH = DeprecatedConstantEnum(FanMode.HIGH, "2025.10")
_DEPRECATED_FAN_TOP = DeprecatedConstantEnum(FanMode.TOP, "2025.10")
_DEPRECATED_FAN_MIDDLE = DeprecatedConstantEnum(FanMode.MIDDLE, "2025.10")
_DEPRECATED_FAN_FOCUS = DeprecatedConstantEnum(FanMode.FOCUS, "2025.10")
_DEPRECATED_FAN_DIFFUSE = DeprecatedConstantEnum(FanMode.DIFFUSE, "2025.10")
FAN_MODES = [cls.value for cls in FanMode]


class SwingMode(StrEnum):
    """Swing mode for climate devices."""

    ON = "on"
    OFF = "off"
    BOTH = "both"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


# These SWING_* constants are deprecated as of Home Assistant 2024.10.
# Please use the ClimateSwingMode enum instead.
_DEPRECATED_SWING_ON = DeprecatedConstantEnum(SwingMode.ON, "2025.10")
_DEPRECATED_SWING_OFF = DeprecatedConstantEnum(SwingMode.OFF, "2025.10")
_DEPRECATED_SWING_BOTH = DeprecatedConstantEnum(SwingMode.BOTH, "2025.10")
_DEPRECATED_SWING_VERTICAL = DeprecatedConstantEnum(SwingMode.VERTICAL, "2025.10")
_DEPRECATED_SWING_HORIZONTAL = DeprecatedConstantEnum(SwingMode.HORIZONTAL, "2025.10")
SWING_MODES = [cls.value for cls in SwingMode]


class HVACAction(StrEnum):
    """HVAC action for climate devices."""

    COOLING = "cooling"
    DEFROSTING = "defrosting"
    DRYING = "drying"
    FAN = "fan"
    HEATING = "heating"
    IDLE = "idle"
    OFF = "off"
    PREHEATING = "preheating"


CURRENT_HVAC_ACTIONS = [cls.value for cls in HVACAction]


ATTR_AUX_HEAT = "aux_heat"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_FAN_MODES = "fan_modes"
ATTR_FAN_MODE = "fan_mode"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_HVAC_ACTION = "hvac_action"
ATTR_HVAC_MODES = "hvac_modes"
ATTR_HVAC_MODE = "hvac_mode"
ATTR_SWING_MODES = "swing_modes"
ATTR_SWING_MODE = "swing_mode"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_TARGET_TEMP_STEP = "target_temp_step"

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = "climate"

SERVICE_SET_AUX_HEAT = "set_aux_heat"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_HUMIDITY = "set_humidity"
SERVICE_SET_HVAC_MODE = "set_hvac_mode"
SERVICE_SET_SWING_MODE = "set_swing_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"


class ClimateEntityFeature(IntFlag):
    """Supported features of the climate entity."""

    TARGET_TEMPERATURE = 1
    TARGET_TEMPERATURE_RANGE = 2
    TARGET_HUMIDITY = 4
    FAN_MODE = 8
    PRESET_MODE = 16
    SWING_MODE = 32
    AUX_HEAT = 64
    TURN_OFF = 128
    TURN_ON = 256


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the ClimateEntityFeature enum instead.
_DEPRECATED_SUPPORT_TARGET_TEMPERATURE = DeprecatedConstantEnum(
    ClimateEntityFeature.TARGET_TEMPERATURE, "2025.1"
)
_DEPRECATED_SUPPORT_TARGET_TEMPERATURE_RANGE = DeprecatedConstantEnum(
    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE, "2025.1"
)
_DEPRECATED_SUPPORT_TARGET_HUMIDITY = DeprecatedConstantEnum(
    ClimateEntityFeature.TARGET_HUMIDITY, "2025.1"
)
_DEPRECATED_SUPPORT_FAN_MODE = DeprecatedConstantEnum(
    ClimateEntityFeature.FAN_MODE, "2025.1"
)
_DEPRECATED_SUPPORT_PRESET_MODE = DeprecatedConstantEnum(
    ClimateEntityFeature.PRESET_MODE, "2025.1"
)
_DEPRECATED_SUPPORT_SWING_MODE = DeprecatedConstantEnum(
    ClimateEntityFeature.SWING_MODE, "2025.1"
)
_DEPRECATED_SUPPORT_AUX_HEAT = DeprecatedConstantEnum(
    ClimateEntityFeature.AUX_HEAT, "2025.1"
)

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
