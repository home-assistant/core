"""
Support for RitAssist Platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ritassist/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

REQUIREMENTS = ['ritassist==0.3']

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
    """Validate the configuration and return a RitAssist scanner."""
    RitAssistDeviceScanner(hass, config, see, discovery_info)
    return True


class RitAssistDeviceScanner:
    """Define a scanner for the RitAssist platform."""

    def __init__(self, hass, config, see, discovery_info):
        """Initialize RitAssistDeviceScanner."""
        from homeassistant.helpers.event import track_utc_time_change
        from ritassist import API

        self._include = config.get(CONF_INCLUDE)
        self._see = see

        self._api = API(config.get(CONF_CLIENT_ID),
                        config.get(CONF_CLIENT_SECRET),
                        config.get(CONF_USERNAME),
                        config.get(CONF_PASSWORD))

        track_utc_time_change(hass,
                              lambda now: self._refresh(),
                              second=range(0, 60, 30))
        self._refresh()

    def _refresh(self) -> None:
        """Refresh device information from the platform."""
        import requests

        try:
            devices = self._api.get_devices()

            for device in devices:
                if (not self._include or device.license_plate in self._include):
                    self._see(dev_id=device.plate_as_id,
                              gps=(device.latitude, device.longitude),
                              attributes=device.state_attributes,
                              icon='mdi:car')

        except requests.exceptions.ConnectionError:
            _LOGGER.error('ConnectionError: Could not connect to RitAssist')
