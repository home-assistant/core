"""Support for an exposed aREST RESTful API of a device."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDevice,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_PIN, CONF_RESOURCE
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_PIN): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the aREST binary sensor."""
    resource = config[CONF_RESOURCE]
    pin = config[CONF_PIN]
    device_class = config.get(CONF_DEVICE_CLASS)

    try:
        response = requests.get(resource, timeout=10).json()
    except requests.exceptions.MissingSchema:
        _LOGGER.error(
            "Missing resource or schema in configuration. Add http:// to your URL"
        )
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", resource)
        return False

    arest = ArestData(resource, pin)

    add_entities(
        [
            ArestBinarySensor(
                arest,
                resource,
                config.get(CONF_NAME, response[CONF_NAME]),
                device_class,
                pin,
            )
        ],
        True,
    )


class ArestBinarySensor(BinarySensorDevice):
    """Implement an aREST binary sensor for a pin."""

    def __init__(self, arest, resource, name, device_class, pin):
        """Initialize the aREST device."""
        self.arest = arest
        self._resource = resource
        self._name = name
        self._device_class = device_class
        self._pin = pin

        if self._pin is not None:
            request = requests.get(f"{self._resource}/mode/{self._pin}/i", timeout=10)
            if request.status_code != 200:
                _LOGGER.error("Can't set mode of %s", self._resource)

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(self.arest.data.get("state"))

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    def update(self):
        """Get the latest data from aREST API."""
        self.arest.update()


class ArestData:
    """Class for handling the data retrieval for pins."""

    def __init__(self, resource, pin):
        """Initialize the aREST data object."""
        self._resource = resource
        self._pin = pin
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from aREST device."""
        try:
            response = requests.get(f"{self._resource}/digital/{self._pin}", timeout=10)
            self.data = {"state": response.json()["return_value"]}
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device '%s'", self._resource)
