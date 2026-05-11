"""Constants for the Watts Vision+ integration."""

from visionpluspython.models import SwitchDevice, ThermostatDevice, ThermostatMode

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    HVACAction,
    HVACMode,
)

DOMAIN = "watts"

OAUTH2_AUTHORIZE = "https://visionlogin.b2clogin.com/visionlogin.onmicrosoft.com/B2C_1A_VISION_UNIFIEDSIGNUPORSIGNIN/oauth2/v2.0/authorize"
OAUTH2_TOKEN = "https://visionlogin.b2clogin.com/visionlogin.onmicrosoft.com/B2C_1A_VISION_UNIFIEDSIGNUPORSIGNIN/oauth2/v2.0/token"

OAUTH2_SCOPES = [
    "openid",
    "offline_access",
    "https://visionlogin.onmicrosoft.com/homeassistant-api/homeassistant.read",
]

# Update intervals
UPDATE_INTERVAL_SECONDS = 30
FAST_POLLING_INTERVAL_SECONDS = 5
DISCOVERY_INTERVAL_MINUTES = 15

# Mapping from Watts Vision+ modes to Home Assistant HVAC modes
THERMOSTAT_MODE_TO_HVAC: dict[ThermostatMode, HVACMode] = {
    ThermostatMode.PROGRAM: HVACMode.AUTO,
    ThermostatMode.ECO: HVACMode.HEAT,
    ThermostatMode.COMFORT: HVACMode.HEAT,
    ThermostatMode.DEFROST: HVACMode.HEAT,
    ThermostatMode.TIMER: HVACMode.HEAT,
    ThermostatMode.OFF: HVACMode.OFF,
}

# Mapping from Home Assistant HVAC modes to Watts Vision+ modes
HVAC_MODE_TO_THERMOSTAT: dict[HVACMode, ThermostatMode] = {
    HVACMode.HEAT: ThermostatMode.COMFORT,
    HVACMode.OFF: ThermostatMode.OFF,
    HVACMode.AUTO: ThermostatMode.PROGRAM,
}

# Preset modes available on all Watts Vision+ thermostats.
PRESET_MODES: list[str] = [PRESET_COMFORT, PRESET_ECO, "defrost", "timer"]

# Mapping from Watts Vision+ mode to HA preset mode string
THERMOSTAT_MODE_TO_PRESET: dict[ThermostatMode, str] = {
    ThermostatMode.COMFORT: PRESET_COMFORT,
    ThermostatMode.ECO: PRESET_ECO,
    ThermostatMode.DEFROST: "defrost",
    ThermostatMode.TIMER: "timer",
}

# Mapping from HA preset mode string to Watts Vision+ ThermostatMode
PRESET_MODE_TO_THERMOSTAT: dict[str, ThermostatMode] = {
    v: k for k, v in THERMOSTAT_MODE_TO_PRESET.items()
}

# Mapping from Watts Vision+ HVAC actions to Home Assistant HVACAction
HVAC_ACTION_TO_HA: dict[str, HVACAction] = {
    "Heating": HVACAction.HEATING,
    "Cooling": HVACAction.COOLING,
    "Idle": HVACAction.IDLE,
    "Off": HVACAction.OFF,
}

SUPPORTED_DEVICE_TYPES = (ThermostatDevice, SwitchDevice)

# Timer service
SERVICE_ACTIVATE_TIMER_MODE = "activate_timer_mode"
ATTR_DURATION = "duration"
