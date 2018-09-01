"""
Support for Logi Circle cameras

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/logi/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

REQUIREMENTS = ['logi_circle==0.1.3']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by circle.logi.com"

NOTIFICATION_ID = 'logi_notification'
NOTIFICATION_TITLE = 'Logi Setup'

DATA_LOGI = 'logi'
DOMAIN = 'logi'
DEFAULT_CACHEDB = '.logi_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'logi'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Logi component."""
    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    try:
        from logi_circle import Logi
        from logi_circle.exception import BadLogin
        from aiohttp.client_exceptions import ClientResponseError

        cache = hass.config.path(DEFAULT_CACHEDB)
        logi = Logi(username=username, password=password, cache_file=cache)
        await logi.login()

        if not logi.is_connected:
            return False
        hass.data['logi'] = await logi.cameras
    except (BadLogin, ClientResponseError) as ex:
        _LOGGER.error('Unable to connect to Logi API: %s', str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True
