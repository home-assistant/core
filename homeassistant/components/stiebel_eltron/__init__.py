"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""
from datetime import timedelta
import logging

from pystiebeleltron import pystiebeleltron
import voluptuous as vol

from homeassistant.components.modbus import (
    CONF_HUB,
    DEFAULT_HUB,
    DOMAIN as MODBUS_DOMAIN,
)
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

DOMAIN = "stiebel_eltron"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the STIEBEL ELTRON unit.

    Will automatically load climate platform.
    """
    name = config[DOMAIN][CONF_NAME]
    modbus_client = hass.data[MODBUS_DOMAIN][config[DOMAIN][CONF_HUB]]

    hass.data[DOMAIN] = {
        "name": name,
        "ste_data": StiebelEltronData(name, modbus_client),
    }

    discovery.load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    return True


class StiebelEltronData:
    """Get the latest data and update the states."""

    def __init__(self, name, modbus_client):
        """Init the STIEBEL ELTRON data object."""

        self.api = pystiebeleltron.StiebelEltronAPI(modbus_client, 1)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update unit data."""
        if not self.api.update():
            _LOGGER.warning("Modbus read failed")
        else:
            _LOGGER.debug("Data updated successfully")
