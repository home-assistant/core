"""Support for BloomSky weather station."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DATA, DOMAIN
from .hub import BloomSky

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_API_KEY): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BloomSky integration."""
    api_key = config[DOMAIN][CONF_API_KEY]

    try:
        bloomsky = BloomSky(api_key, hass.config.units is METRIC_SYSTEM)
    except RuntimeError:
        return False

    hass.data[DATA] = bloomsky

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
