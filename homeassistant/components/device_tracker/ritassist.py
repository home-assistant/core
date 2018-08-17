"""
Support for RitAssist Platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ritassist/
"""
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.event import track_utc_time_change

REQUIREMENTS = ['ritassist==0.5']

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_INCLUDE = 'include'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
    vol.Optional(CONF_INCLUDE, default=[]):
        vol.All(cv.ensure_list, [cv.string])
})


def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Set up the DeviceScanner and check if login is valid."""
    scanner = RitAssistDeviceScanner(config, see)
    if not scanner.login(hass):
        _LOGGER.error('RitAssist authentication failed')
        return False
    return True


class RitAssistDeviceScanner:
    """Define a scanner for the RitAssist platform."""

    def __init__(self, config, see):
        """Initialize RitAssistDeviceScanner."""
        from ritassist import API

        self._include = config.get(CONF_INCLUDE)
        self._see = see

        self._api = API(config.get(CONF_CLIENT_ID),
                        config.get(CONF_CLIENT_SECRET),
                        config.get(CONF_USERNAME),
                        config.get(CONF_PASSWORD))

    def setup(self, hass):
        """Setup a timer and start gathering devices."""
        self._refresh()
        track_utc_time_change(hass,
                              lambda now: self._refresh(),
                              second=range(0, 60, 30))

    def login(self, hass):
        """Perform a login on the RitAssist API."""
        if self._api.login():
            self.setup(hass)
            return True
        return False

    def _refresh(self) -> None:
        """Refresh device information from the platform."""
        try:
            devices = self._api.get_devices()

            for device in devices:
                if (not self._include or
                        device.license_plate in self._include):
                    self._see(dev_id=device.plate_as_id,
                              gps=(device.latitude, device.longitude),
                              attributes=device.state_attributes,
                              icon='mdi:car')

        except requests.exceptions.ConnectionError:
            _LOGGER.error('ConnectionError: Could not connect to RitAssist')
