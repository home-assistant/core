"""
homeassistant.components.bloomsky
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/bloomsky/
"""
import logging
from datetime import timedelta
import requests
from homeassistant.util import Throttle
from homeassistant.helpers import validate_config
from homeassistant.const import CONF_API_KEY

DOMAIN = "bloomsky"
BLOOMSKY = None

_LOGGER = logging.getLogger(__name__)

# the BloomSky only updates every 5-8 minutes as per the API spec so there's
# no point in polling the API more frequently
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)


# pylint: disable=unused-argument
def setup(hass, config):
    """
    Setup BloomSky component.
    """
    if not validate_config(
            config,
            {DOMAIN: [CONF_API_KEY]},
            _LOGGER):
        return False

    api_key = config[DOMAIN][CONF_API_KEY]

    global BLOOMSKY
    BLOOMSKY = BloomSky(api_key)

    return True


class BloomSky(object):
    """Handle all communication with the BloomSky API"""

    # API documentation at http://weatherlution.com/bloomsky-api/

    API_URL = "https://api.bloomsky.com/api/skydata"

    def __init__(self, api_key):
        self._logger = logging.getLogger(__name__)
        self._api_key = api_key
        self.devices = {}
        self._logger.debug("Initial bloomsky device load...")
        self.refresh_devices()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_devices(self):
        """
        Uses the API to retreive a list of devices associated with an
        account along with all the sensors on the device.
        """
        self._logger.debug("Fetching bloomsky update")
        response = requests.get(self.API_URL,
                                headers={"Authorization": self._api_key})
        if response.status_code != 200:
            self._logger.error("Invalid HTTP response: %s",
                               response.status_code)
            return
        # create dictionary keyed off of the device unique id
        for device in response.json():
            device_id = device["DeviceID"]
            self.devices[device_id] = device
