"""Constants for the MirAIe AC integration."""

from py_miraie_ac import (
    FanMode as MirAIeFanMode,
    HVACMode as MirAIeHVACMode,
    PresetMode as MirAIePresetMode,
)

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACMode,
)

DOMAIN = "miraie_ac"
CONFIG_KEY_USER_ID = "mobile"

# max and min values supported by the devices
MAX_TEMP = 30.0
MIN_TEMP = 16.0

HVAC_MODE_MAP_TO_HASS = {
    MirAIeHVACMode.COOL: HVACMode.COOL,
    MirAIeHVACMode.AUTO: HVACMode.AUTO,
    MirAIeHVACMode.DRY: HVACMode.DRY,
    MirAIeHVACMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_MAP_TO_MIRAIE = {
    HVACMode.AUTO: MirAIeHVACMode.AUTO,
    HVACMode.COOL: MirAIeHVACMode.COOL,
    HVACMode.DRY: MirAIeHVACMode.DRY,
    HVACMode.FAN_ONLY: MirAIeHVACMode.FAN,
}

PRESET_MODE_MAP_TO_HASS = {
    MirAIePresetMode.BOOST: PRESET_BOOST,
    MirAIePresetMode.ECO: PRESET_ECO,
    MirAIePresetMode.NONE: PRESET_NONE,
}

PRESET_MODE_MAP_TO_MIRAIE = {
    PRESET_BOOST: MirAIePresetMode.BOOST,
    PRESET_ECO: MirAIePresetMode.ECO,
    PRESET_NONE: MirAIePresetMode.NONE,
}

FAN_MODE_MAP_TO_HASS = {
    MirAIeFanMode.AUTO: FAN_AUTO,
    MirAIeFanMode.HIGH: FAN_HIGH,
    MirAIeFanMode.LOW: FAN_LOW,
    MirAIeFanMode.MEDIUM: FAN_MEDIUM,
    MirAIeFanMode.QUIET: FAN_OFF,
}

FAN_MODE_MAP_TO_MIRAIE = {
    FAN_AUTO: MirAIeFanMode.AUTO,
    FAN_HIGH: MirAIeFanMode.HIGH,
    FAN_LOW: MirAIeFanMode.LOW,
    FAN_MEDIUM: MirAIeFanMode.MEDIUM,
    FAN_OFF: MirAIeFanMode.QUIET,
}


SUPPORTED_HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.OFF,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]

SUPPORTED_PRESET_MODES = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
SUPPORTED_FAN_MODES = [
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,
]

SUPPORTED_SWING_MODES = [
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
]

SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.SWING_MODE
)
