"""
Support for OhmConnect.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.ohmconnect/
"""
import logging
from datetime import timedelta
import xml.etree.ElementTree as ET
import requests

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the OhmConnect sensors."""
    ohmid = config.get("id")
    if ohmid is None:
        _LOGGER.error("You must provide your OhmConnect ID!")
        return False

    add_devices([OhmconnectSensor(config.get("name", "OhmConnect Status"),
                                  ohmid)])


class OhmconnectSensor(Entity):
    """Representation of a OhmConnect sensor."""

    def __init__(self, name, ohmid):
        """Initialize the sensor."""
        self._name = name
        self._ohmid = ohmid
        self._data = {}
        self.update()

    @property
    def name(self):
        """The name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._data["active"] == "True":
            return "Active"
        else:
            return "Inactive"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"Address": self._data["address"], "ID": self._ohmid}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from OhmConnect."""
        try:
            url = ("https://login.ohmconnect.com"
                   "/verify-ohm-hour/{}").format(self._ohmid)
            response = requests.get(url, timeout=10)
            root = ET.fromstring(response.text)

            for child in root:
                self._data[child.tag] = child.text
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to host/endpoint: %s", url)
            self.data = {}
