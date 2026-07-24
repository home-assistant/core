"""Constants for the Velux integration."""

from logging import getLogger

from pyvlx import PyVLX

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN = "velux"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SWITCH,
]
LOGGER = getLogger(__package__)

PYVLX_FROM_CONFIG_FLOW: HassKey[dict[str, PyVLX]] = HassKey(
    "velux_pyvlx_from_config_flow"
)
