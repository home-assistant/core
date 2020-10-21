"""This component provides support for Stookalert Binary Sensor."""
from datetime import timedelta

import stookalert
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers import config_validation as cv

SCAN_INTERVAL = timedelta(minutes=60)
CONF_PROVINCE = "province"
DEFAULT_DEVICE_CLASS = DEVICE_CLASS_SAFETY
DEFAULT_NAME = "Stookalert"
ATTRIBUTION = "Data provided by rivm.nl"
PROVINCES = [
    "Drenthe",
    "Flevoland",
    "Friesland",
    "Gelderland",
    "Groningen",
    "Limburg",
    "Noord-Brabant",
    "Noord-Holland",
    "Overijssel",
    "Utrecht",
    "Zeeland",
    "Zuid-Holland",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PROVINCE): vol.In(PROVINCES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Stookalert binary sensor platform."""
    province = config[CONF_PROVINCE]
    name = config[CONF_NAME]
    api_handler = stookalert.stookalert(province)
    add_entities([StookalertBinarySensor(name, api_handler)], update_before_add=True)


class StookalertBinarySensor(BinarySensorEntity):
    """An implementation of RIVM Stookalert."""

    def __init__(self, name, api_handler):
        """Initialize a Stookalert device."""
        self._name = name
        self._api_handler = api_handler

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor."""
        state_attr = {ATTR_ATTRIBUTION: ATTRIBUTION}

        if self._api_handler.last_updated is not None:
            state_attr["last_updated"] = self._api_handler.last_updated.isoformat()

        return state_attr

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the Alert is active."""
        return self._api_handler.state == 1

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return DEFAULT_DEVICE_CLASS

    def update(self):
        """Update the data from the Stookalert handler."""
        self._api_handler.get_alerts()
