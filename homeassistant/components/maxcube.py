"""
Platform for the MAX! Cube LAN Gateway.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/maxcube/
"""

from socket import timeout
import logging
import time
from threading import Lock

from homeassistant.helpers.discovery import load_platform
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['maxcube-api==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'maxcube'
MAXCUBE_HANDLE = 'maxcube'

DEFAULT_PORT = 62910

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Establish connection to MAX! Cube."""
    from maxcube.connection import MaxCubeConnection
    from maxcube.cube import MaxCube

    # Read Config
    host = config.get(DOMAIN).get(CONF_HOST)
    port = config.get(DOMAIN).get(CONF_PORT)

    # Assign Cube Handle to global variable
    try:
        cube = MaxCube(MaxCubeConnection(host, port))
    except timeout:
        _LOGGER.error("Connection to Max!Cube could not be established")
        cube = None
        return False

    hass.data[MAXCUBE_HANDLE] = MaxCubeHandle(cube)

    # Load Climate (for Thermostats)
    load_platform(hass, 'climate', DOMAIN)

    # Load BinarySensor (for Window Shutter)
    load_platform(hass, 'binary_sensor', DOMAIN)

    # Initialization successfull
    return True


class MaxCubeHandle(object):
    """Keep the cube instance in one place and centralize the update."""

    def __init__(self, cube):
        """Initialize the Cube Handle."""
        # Cube handle
        self.cube = cube

        # Instantiate Mutex
        self.mutex = Lock()

        # Update Timestamp
        self._updatets = time.time()

    def update(self):
        """Pull the latest data from the MAX! Cube."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            # Only update every 60s
            if (time.time() - self._updatets) >= 60:
                _LOGGER.debug("UPDATE: Updating")

                try:
                    self.cube.update()
                except timeout:
                    _LOGGER.error("Max!Cube connection failed")
                    return False

                self._updatets = time.time()
            else:
                _LOGGER.debug("UPDATE: Skipping")
