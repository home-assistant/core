"""Binary Sensor for MeteoAlarm.eu."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_COUNTRY = 'country'
CONF_PROVINCE = 'province'
CONF_LANGUAGE = 'language'

ATTRIBUTION = "Information provided by MeteoAlarm."

DEFAULT_NAME = 'meteoalarm'
DEFAULT_DEVICE_CLASS = 'safety'

ICON = 'mdi:alert'

SCAN_INTERVAL = timedelta(minutes=30)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COUNTRY): cv.string,
    vol.Required(CONF_PROVINCE): cv.string,
    vol.Optional(CONF_LANGUAGE, default='en'): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MeteoAlarm binary sensor platform."""
    from meteoalertapi import Meteoalert

    country = config[CONF_COUNTRY]
    province = config[CONF_PROVINCE]
    language = config[CONF_LANGUAGE]
    name = config[CONF_NAME]

    try:
        api = Meteoalert(country, province, language)
    except KeyError():
        _LOGGER.error("Wrong country digits, or province name")
        return

    add_entities([MeteoAlertBinarySensor(api, name)], True)


class MeteoAlertBinarySensor(BinarySensorDevice):
    """Representation of a MeteoAlert binary sensor."""

    def __init__(self, api, name):
        """Initialize the MeteoAlert binary sensor."""
        self._name = name
        self._attributes = {}
        self._state = None
        self._api = api

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return DEFAULT_DEVICE_CLASS

    def update(self):
        """Update device state."""
        alert = self._api.get_alert()
        if alert:
            self._attributes = alert
            self._state = True
        else:
            self._attributes = {}
            self._state = False
