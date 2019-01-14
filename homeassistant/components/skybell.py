"""
Support for the Skybell HD Doorbell.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/skybell/
"""
import logging

from requests.exceptions import HTTPError, ConnectTimeout
import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['skybellpy==0.3.0']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Skybell.com"

NOTIFICATION_ID = 'skybell_notification'
NOTIFICATION_TITLE = 'Skybell Sensor Setup'

DOMAIN = 'skybell'
DEFAULT_CACHEDB = './skybell_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'skybell'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Skybell component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        from skybellpy import Skybell

        cache = hass.config.path(DEFAULT_CACHEDB)
        skybell = Skybell(username=username, password=password,
                          get_devices=True, cache_path=cache)

        hass.data[DOMAIN] = skybell
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Skybell service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True


class SkybellDevice(Entity):
    """A HA implementation for Skybell devices."""

    def __init__(self, device):
        """Initialize a sensor for Skybell device."""
        self._device = device

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def update(self):
        """Update automation state."""
        self._device.refresh()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'device_id': self._device.device_id,
            'status': self._device.status,
            'location': self._device.location,
            'wifi_ssid': self._device.wifi_ssid,
            'wifi_status': self._device.wifi_status,
            'last_check_in': self._device.last_check_in,
            'motion_threshold': self._device.motion_threshold,
            'video_profile': self._device.video_profile,
        }
