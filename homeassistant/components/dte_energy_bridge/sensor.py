"""Support for monitoring energy usage using the DTE energy bridge."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, HTTP_OK
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_IP_ADDRESS = "ip"
CONF_VERSION = "version"

DEFAULT_NAME = "Current Energy Usage"
DEFAULT_VERSION = 1

ICON = "mdi:flash"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.All(
            vol.Coerce(int), vol.Any(1, 2)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DTE energy bridge sensor."""
    name = config.get(CONF_NAME)
    ip_address = config.get(CONF_IP_ADDRESS)
    version = config.get(CONF_VERSION, 1)

    add_entities([DteEnergyBridgeSensor(ip_address, name, version)], True)


class DteEnergyBridgeSensor(Entity):
    """Implementation of the DTE Energy Bridge sensors."""

    def __init__(self, ip_address, name, version):
        """Initialize the sensor."""
        self._version = version

        if self._version == 1:
            self._url = f"http://{ip_address}/instantaneousdemand"
        elif self._version == 2:
            self._url = f"http://{ip_address}:8888/zigbee/se/instantaneousdemand"

        self._name = name
        self._unit_of_measurement = "kW"
        self._state = None

    @property
    def name(self):
        """Return the name of th sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the energy usage data from the DTE energy bridge."""
        try:
            response = requests.get(self._url, timeout=5)
        except (requests.exceptions.RequestException, ValueError):
            _LOGGER.warning(
                "Could not update status for DTE Energy Bridge (%s)", self._name
            )
            return

        if response.status_code != HTTP_OK:
            _LOGGER.warning(
                "Invalid status_code from DTE Energy Bridge: %s (%s)",
                response.status_code,
                self._name,
            )
            return

        response_split = response.text.split()

        if len(response_split) != 2:
            _LOGGER.warning(
                'Invalid response from DTE Energy Bridge: "%s" (%s)',
                response.text,
                self._name,
            )
            return

        val = float(response_split[0])

        # A workaround for a bug in the DTE energy bridge.
        # The returned value can randomly be in W or kW.  Checking for a
        # a decimal seems to be a reliable way to determine the units.
        # Limiting to version 1 because version 2 apparently always returns
        # values in the format 000000.000 kW, but the scaling is Watts
        # NOT kWatts
        if self._version == 1 and "." in response_split[0]:
            self._state = val
        else:
            self._state = val / 1000
