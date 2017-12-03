"""
Support for Ring Doorbell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/ring/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['ring_doorbell==0.1.8']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = 'ring_notification'
NOTIFICATION_TITLE = 'Ring Setup'

DATA_RING = 'ring'
DOMAIN = 'ring'
DEFAULT_CACHEDB = '.ring_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'ring'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Ring component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        from ring_doorbell import Ring

        cache = hass.config.path(DEFAULT_CACHEDB)
        ring = Ring(username=username, password=password, cache_file=cache)
        if not ring.is_connected:
            return False
        hass.data['ring'] = ring
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True
