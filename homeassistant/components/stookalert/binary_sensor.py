"""This component provides support for Stookalert Binary Sensor."""
import logging
import voluptuous as vol
import stookalert
from datetime import timedelta

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)
CONF_PROVINCE = "province"
DEFAULT_NAME = "Stookalert"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
		vol.Required(CONF_PROVINCE): vol.In([
            "drenthe", "flevoland", "friesland", "gelderland", "groningen", "limburg", 
            "noord-brabant", "noord-holland", "overijssel", "utrecht", "zeeland", "zuid-holland"]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    })


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the binary sensor platform"""
    add_devices([Stookalert(config)], update_before_add=True)


class Stookalert(Entity):
    """An implementation of RIVM Stookalert"""

    def __init__(self, config):
        """Initialize a Stookalert device."""
        self._province = config.get(CONF_PROVINCE)
        self._apiHandler = stookalert.stookalert(self._province)
        self._name = config.get(CONF_NAME)

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""
        state_attr = self._apiHandler._alerts.copy()
        if self._apiHandler._last_updated is not None:
            state_attr["last_updated"] = self._apiHandler._last_updated.strftime('%d-%m-%Y %H:%M:%S')
        return state_attr

    @property
    def name(self):
        """Return the name of the sensor"""
        return self._name

    @property
    def should_poll(self):
        """Polling needed for the device status."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._apiHandler._state == 0:
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
        """Update the data from the camera."""
        self._apiHandler.get_alert()
