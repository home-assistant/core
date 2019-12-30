"""This component provides support for Stookalert Binary Sensor."""
from datetime import timedelta
import logging

import stookalert
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)
CONF_PROVINCE = "province"
DEFAULT_NAME = "Stookalert"
PROVINCES = [
    "drenthe",
    "flevoland",
    "friesland",
    "gelderland",
    "groningen",
    "limburg",
    "noord-brabant",
    "noord-holland",
    "overijssel",
    "utrecht",
    "zeeland",
    "zuid-holland",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PROVINCE): vol.In(PROVINCES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Stookalert binary sensor platform."""
    add_devices([Stookalert(config)], update_before_add=True)


class Stookalert(Entity):
    """An implementation of RIVM Stookalert."""

    def __init__(self, config):
        """Initialize a Stookalert device."""
        self._province = config.get(CONF_PROVINCE)
        self._api_handler = stookalert.stookalert(self._province)
        self._name = config.get(CONF_NAME)

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor."""
        state_attr = self._api_handler._alerts.copy()
        if self._api_handler._last_updated is not None:
            state_attr["last_updated"] = self._api_handler._last_updated.strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        return state_attr

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._api_handler._state == 0:
            return STATE_OFF
        else:
            return STATE_ON

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self.state == STATE_ON:
            return "mdi:alert"
        else:
            return "mdi:check"

    def update(self):
        """Update the data from the Stookalert handler."""
        self._api_handler.get_alert()
