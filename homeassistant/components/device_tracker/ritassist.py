"""
Support for RitAssist Platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ritassist/
"""
import logging
import voluptuous as vol

from ritassist import (API, Authentication)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

REQUIREMENTS = ['ritassist==0.3']

_LOGGER = logging.getLogger(__name__)

CLIENT_UUID_CONFIG_FILE = '.ritassist.conf'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_INCLUDE = 'include'
CONF_INTERVAL = 'interval'

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

        self._discovery_info = discovery_info
        self._hass = hass
        self._devices = []
        self._config = config
        self._see = see

        self._file = self._hass.config.path(CLIENT_UUID_CONFIG_FILE)
        self._authentication_info = self.load_authentication(self._file)

        self._api = API(self._config.get(CONF_CLIENT_ID),
                        self._config.get(CONF_CLIENT_SECRET),
                        self._config.get(CONF_USERNAME),
                        self._config.get(CONF_PASSWORD))

        track_utc_time_change(self._hass,
                              lambda now: self._refresh(),
                              second=range(0, 60, 30))
        self._refresh()

    @property
    def devices(self):
        """Return the devices detected."""
        return self._devices

    def _refresh(self) -> None:
        """Refresh device information from the platform."""
        import requests

        try:
            include = self._config.get(CONF_INCLUDE)
            self._devices = self._api.get_devices()

            for device in self._devices:
                if (not include or device.license_plate in include):
                    self._see(dev_id=device.plate_as_id,
                              gps=(device.latitude, device.longitude),
                              attributes=device.state_attributes,
                              icon='mdi:car')            

        except requests.exceptions.ConnectionError:
            _LOGGER.error('ConnectionError: Could not connect to RitAssist')

    def save_authentication(self, filename):
        """Save the authentication information to a file for caching."""
        from homeassistant.util.json import save_json

        json = {
            'access_token': self._authentication_info.access_token,
            'refresh_token': self._authentication_info.refresh_token,
            'expires_in': self._authentication_info.expires_in,
            'authenticated': self._authentication_info.authenticated
        }
        if not save_json(filename, json):
            _LOGGER.error("Failed to save configuration file")

    def load_authentication(self, filename):
        """Load the authentication information from a file for caching."""
        from homeassistant.util.json import load_json

        data = load_json(filename)
        if data:
            result = Authentication()
            result.set_json(data)
            if not result.is_valid():
                return None

            return result
        else:
            return None
