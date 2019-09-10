"""Support for Obihai Sensors."""
import logging

from datetime import timedelta
import voluptuous as vol

from pyobihai import PyObihai

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_TIMESTAMP,
)

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

OBIHAI = "Obihai"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Obihai sensor platform."""

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    host = config[CONF_HOST]

    sensors = []

    pyobihai = PyObihai()

    services = pyobihai.get_state(host, username, password)

    line_services = pyobihai.get_line_state(host, username, password)

    for key in services:
        sensors.append(ObihaiServiceSensors(pyobihai, host, username, password, key))

    for key in line_services:
        sensors.append(ObihaiServiceSensors(pyobihai, host, username, password, key))

    add_entities(sensors)


class ObihaiServiceSensors(Entity):
    """Get the status of each Obihai Lines."""

    def __init__(self, pyobihai, host, username, password, service_name):
        """Initialize monitor sensor."""
        self._host = host
        self._username = username
        self._password = password
        self._service_name = service_name
        self._state = None
        self._name = f"{OBIHAI} {self._service_name}"
        self._pyobihai = pyobihai

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class for uptime sensor."""
        if self._service_name == "Last Reboot":
            return DEVICE_CLASS_TIMESTAMP
        return None

    def update(self):
        """Update the sensor."""
        services = self._pyobihai.get_state(self._host, self._username, self._password)

        if self._service_name in services:
            self._state = services.get(self._service_name)

        services = self._pyobihai.get_line_state(
            self._host, self._username, self._password
        )

        if self._service_name in services:
            self._state = services.get(self._service_name)
