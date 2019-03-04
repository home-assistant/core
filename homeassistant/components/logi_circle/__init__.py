"""Support for Logi Circle devices."""
import asyncio
import logging

import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['logi_circle==0.1.7']

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 15  # seconds

ATTRIBUTION = "Data provided by circle.logi.com"

NOTIFICATION_ID = 'logi_notification'
NOTIFICATION_TITLE = 'Logi Circle Setup'

DOMAIN = 'logi_circle'
DEFAULT_CACHEDB = '.logi_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'logi_circle'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Logi Circle component."""
    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    try:
        from logi_circle import Logi
        from logi_circle.exception import BadLogin
        from aiohttp.client_exceptions import ClientResponseError

        cache = hass.config.path(DEFAULT_CACHEDB)
        logi = Logi(username=username, password=password, cache_file=cache)

        with async_timeout.timeout(_TIMEOUT, loop=hass.loop):
            await logi.login()
            hass.data[DOMAIN] = await logi.cameras

        if not logi.is_connected:
            return False
    except (BadLogin, ClientResponseError) as ex:
        _LOGGER.error('Unable to connect to Logi Circle API: %s', str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    except asyncio.TimeoutError:
        # The TimeoutError exception object returns nothing when casted to a
        # string, so we'll handle it separately.
        err = '{}s timeout exceeded when connecting to Logi Circle API'.format(
            _TIMEOUT)
        _LOGGER.error(err)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    return True
