"""Constants for the GKP integration."""

from datetime import timedelta

from gkphomepython import GkpMode

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    HVACMode,
)

DOMAIN = "gkp"

OAUTH2_AUTHORIZE = "https://gkp-id-prd.azurewebsites.net/connect/authorize"
OAUTH2_TOKEN = "https://gkp-id-prd.azurewebsites.net/connect/token"

OAUTH2_SCOPES = [
    "openid",
    "offline_access",
    "Installation.Read",
    "IOTManagement.Read",
    "IOTManagement.Write",
]

UPDATE_INTERVAL = timedelta(minutes=2)
FAST_POLLING_INTERVAL = timedelta(seconds=5)
DISCOVERY_INTERVAL = timedelta(minutes=15)

PRESET_DEFROST = "defrost"

GKP_MODE_TO_HVAC: dict[GkpMode, HVACMode] = {
    GkpMode.OFF: HVACMode.OFF,
    GkpMode.AUTO: HVACMode.AUTO,
    GkpMode.ECO: HVACMode.HEAT,
    GkpMode.COMFORT: HVACMode.HEAT,
    GkpMode.DEFROST: HVACMode.HEAT,
    GkpMode.BOOST: HVACMode.HEAT,
}

HVAC_TO_GKP_MODE: dict[HVACMode, GkpMode] = {
    HVACMode.OFF: GkpMode.OFF,
    HVACMode.AUTO: GkpMode.AUTO,
    HVACMode.HEAT: GkpMode.COMFORT,
}

GKP_MODE_TO_PRESET: dict[GkpMode, str] = {
    GkpMode.COMFORT: PRESET_COMFORT,
    GkpMode.ECO: PRESET_ECO,
    GkpMode.BOOST: PRESET_BOOST,
    GkpMode.DEFROST: PRESET_DEFROST,
}

PRESET_TO_GKP_MODE: dict[str, GkpMode] = {v: k for k, v in GKP_MODE_TO_PRESET.items()}

PRESET_MODES: list[str] = list(GKP_MODE_TO_PRESET.values())
