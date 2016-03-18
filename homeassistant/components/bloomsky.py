"""
Support for BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/bloomsky/
"""
import logging
from datetime import timedelta

import requests

from homeassistant.components import discovery
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle

DOMAIN = "bloomsky"
BLOOMSKY = None

_LOGGER = logging.getLogger(__name__)

# The BloomSky only updates every 5-8 minutes as per the API spec so there's
# no point in polling the API more frequently
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

DISCOVER_SENSORS = 'bloomsky.sensors'
DISCOVER_BINARY_SENSORS = 'bloomsky.binary_sensor'
DISCOVER_CAMERAS = 'bloomsky.camera'


# pylint: disable=unused-argument,too-few-public-methods
def setup(hass, config):
    """Setup BloomSky component."""
    if not validate_config(
            config,
            {DOMAIN: [CONF_API_KEY]},
            _LOGGER):
        return False

    api_key = config[DOMAIN][CONF_API_KEY]

    global BLOOMSKY
    try:
        BLOOMSKY = BloomSky(api_key)
    except RuntimeError:
        return False

    for component, discovery_service in (
            ('camera', DISCOVER_CAMERAS), ('sensor', DISCOVER_SENSORS),
            ('binary_sensor', DISCOVER_BINARY_SENSORS)):
        discovery.discover(hass, discovery_service, component=component,
                           hass_config=config)

    return True


class BloomSky(object):
    """Handle all communication with the BloomSky API."""

    # API documentation at http://weatherlution.com/bloomsky-api/
    API_URL = "https://api.bloomsky.com/api/skydata"

    def __init__(self, api_key):
        """Initialize the BookSky."""
        self._api_key = api_key
        self.devices = {}
        _LOGGER.debug("Initial bloomsky device load...")
        self.refresh_devices()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_devices(self):
        """Use the API to retreive a list of devices."""
        _LOGGER.debug("Fetching bloomsky update")
        response = requests.get(self.API_URL,
                                headers={"Authorization": self._api_key},
                                timeout=10)
        if response.status_code == 401:
            raise RuntimeError("Invalid API_KEY")
        elif response.status_code != 200:
            _LOGGER.error("Invalid HTTP response: %s", response.status_code)
            return
        # Create dictionary keyed off of the device unique id
        self.devices.update({
            device["DeviceID"]: device for device in response.json()
        })
