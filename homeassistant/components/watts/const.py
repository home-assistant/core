"""Constants for the Watts Vision+ integration."""

from visionpluspython.models import ThermostatMode

from homeassistant.components.climate import HVACMode

DOMAIN = "watts"

OAUTH2_AUTHORIZE = "https://visionlogin.b2clogin.com/visionlogin.onmicrosoft.com/B2C_1A_VISION_UNIFIEDSIGNUPORSIGNIN/oauth2/v2.0/authorize"
OAUTH2_TOKEN = "https://visionlogin.b2clogin.com/visionlogin.onmicrosoft.com/B2C_1A_VISION_UNIFIEDSIGNUPORSIGNIN/oauth2/v2.0/token"

OAUTH2_SCOPES = [
    "openid",
    "offline_access",
    "https://visionlogin.onmicrosoft.com/homeassistant-api/homeassistant.read",
]

UPDATE_INTERVAL = 30
FAST_POLLING_INTERVAL = 5

# Mapping from Watts Vision + modes to Home Assistant HVAC modes

THERMOSTAT_MODE_TO_HVAC = {
    "Program": HVACMode.AUTO,
    "Eco": HVACMode.HEAT,
    "Comfort": HVACMode.HEAT,
    "Off": HVACMode.OFF,
}

# Mapping from Home Assistant HVAC modes to Watts Vision + modes
HVAC_MODE_TO_THERMOSTAT = {
    HVACMode.HEAT: ThermostatMode.COMFORT,
    HVACMode.OFF: ThermostatMode.OFF,
    HVACMode.AUTO: ThermostatMode.PROGRAM,
}
