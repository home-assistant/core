"""
Support for Ring Doorbell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/ring/
"""
from datetime import timedelta
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.loader as loader

from requests.exceptions import HTTPError, ConnectTimeout


REQUIREMENTS = ['ring_doorbell==0.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = 'ring_notification'
NOTIFICATION_TITLE = 'Ring Sensor Setup'

DOMAIN = 'ring'
DEFAULT_CACHEDB = 'ring_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'ring'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
SCAN_INTERVAL = timedelta(seconds=5)

RING = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Ring component."""
    global RING
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    persistent_notification = loader.get_component('persistent_notification')
    try:
        from ring_doorbell import Ring

        ring = Ring(username, password)
        if ring.is_connected:
            RING = RingData(ring)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        persistent_notification.create(
            hass, 'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True


class RingData(object):
    """Stores the data retrived for Ring device."""

    def __init__(self, data):
        """Initialize the data object."""
        self.data = data
