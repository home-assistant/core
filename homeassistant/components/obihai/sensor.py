"""Support for Obihai Sensors."""
import logging

from datetime import timedelta
import voluptuous as vol

from pyobihai import PyObihai

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

DOMAIN = "Obihai"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Obihai sensor platform."""

    username = config.get(CONF_USERNAME, None)
    password = config.get(CONF_PASSWORD, None)
    host = config.get(CONF_HOST, None)

    sensors = []

    pyobihai = PyObihai()

    services = pyobihai.get_state(host, username, password)

    line_services = pyobihai.get_line_state(host, username, password)

    for key in services:
        sensors.append(ObihaiServiceSensors(host, username, password, key))

    for key in line_services:
        sensors.append(ObihaiServiceSensors(host, username, password, key))

    add_devices(sensors)


class ObihaiServiceSensors(Entity):
    """Get the status of each Obihai Lines."""

    def __init__(self, host, username, password, service_name):
        """Initialize monitor sensor."""
        self._host = host
        self._username = username
        self._password = password
        self._service_name = service_name
        self._state = None
        self._name = "{} {}".format(DOMAIN, self._service_name)
        self._pyobihai = PyObihai()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        services = self._pyobihai.get_state(self._host, self._username, self._password)

        if self._service_name in services:
            if services[self._service_name] is None:
                self._state = STATE_UNKNOWN
            else:
                self._state = services[self._service_name]

        services = self._pyobihai.get_line_state(
            self._host, self._username, self._password
        )

        if self._service_name in services:
            if services[self._service_name] is None:
                self._state = STATE_UNKNOWN
            else:
                self._state = services[self._service_name]
