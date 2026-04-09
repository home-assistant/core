"""Constants for the Watts Vision+ integration."""

from visionpluspython.models import SwitchDevice, ThermostatDevice, ThermostatMode

from homeassistant.components.climate import HVACAction, HVACMode

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
THERMOSTAT_MODE_TO_HVAC: dict[str, HVACMode] = {
    "Program": HVACMode.AUTO,
    "Eco": HVACMode.HEAT,
    "Comfort": HVACMode.HEAT,
    "Off": HVACMode.OFF,
}

# Mapping from Home Assistant HVAC modes to Watts Vision+ modes
HVAC_MODE_TO_THERMOSTAT: dict[HVACMode, ThermostatMode] = {
    HVACMode.HEAT: ThermostatMode.COMFORT,
    HVACMode.OFF: ThermostatMode.OFF,
    HVACMode.AUTO: ThermostatMode.PROGRAM,
}

# Mapping from Watts Vision+ HVAC actions to Home Assistant HVACAction
HVAC_ACTION_TO_HA: dict[str, HVACAction] = {
    "Heating": HVACAction.HEATING,
    "Cooling": HVACAction.COOLING,
    "Idle": HVACAction.IDLE,
    "Off": HVACAction.OFF,
}

SUPPORTED_DEVICE_TYPES = (ThermostatDevice, SwitchDevice)
