"""
Support for DoorBird device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/doorbird/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_USERNAME, \
    CONF_PASSWORD, CONF_NAME, CONF_DEVICES

REQUIREMENTS = ['DoorBirdPy==0.1.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbird'

API_URL = '/api/{}'.format(DOMAIN)

CONF_DOORBELL_EVENTS = 'doorbell_events'
CONF_CUSTOM_URL = 'hass_url_override'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CUSTOM_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])
    }),
}, extra=vol.ALLOW_EXTRA)

SENSOR_DOORBELL = 'doorbell'


def setup(hass, config):
    """Set up the DoorBird component."""
    from doorbirdpy import DoorBird

    doorstations = []

    for index, doorstation_config in enumerate(config[DOMAIN][CONF_DEVICES]):
        device_ip = doorstation_config.get(CONF_HOST)
        username = doorstation_config.get(CONF_USERNAME)
        password = doorstation_config.get(CONF_PASSWORD)
        custom_url = doorstation_config.get(CONF_CUSTOM_URL)
        name = (doorstation_config.get(CONF_NAME)
                or 'DoorBird {}'.format(index + 1))

        device = DoorBird(device_ip, username, password)
        status = device.ready()

        if status[0]:
            _LOGGER.info("Connected to DoorBird at %s as %s", device_ip,
                         username)
            doorstations.append(ConfiguredDoorbird(device, name, custom_url))
        elif status[1] == 401:
            _LOGGER.error("Authorization rejected by DoorBird at %s",
                          device_ip)
            return False
        else:
            _LOGGER.error("Could not connect to DoorBird at %s: Error %s",
                          device_ip, str(status[1]))
            return False

    hass.data[DOMAIN] = doorstations

    return True


class ConfiguredDoorbird():
    """Attach additional information to pass along with configured device."""

    def __init__(self, device, name, custom_url = None):
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url

    @property
    def name(self):
        """Custom device name."""
        return self._name

    @property
    def device(self):
        """The configured device."""
        return self._device

    @property
    def custom_url(self):
        """Custom url for device."""
        return self._custom_url
