import asyncio
import logging
import voluptuous as vol

from homeassistant.const import (CONF_API_KEY, CONF_HOST, CONF_PASSWORD,
                                 CONF_PORT, CONF_USERNAME,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv

# REQUIREMENTS = ['deconz==xx']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'deconz'

DECONZ = None

CONF_WS_PORT = 'websocket_port'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_WS_PORT, default=443): cv.port,
        vol.Optional(CONF_USERNAME, default='delight'): cv.string,
        vol.Optional(CONF_PASSWORD, default='delight'): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """
    """
    deconz_config = config[DOMAIN]

    @asyncio.coroutine
    def generate_api_key(call):
        """
        """
        from .deconz_lib import get_api_key
        api_key = yield from get_api_key(**deconz_config)
        hass.states.async_set('deconz.api_key', api_key)
        deconz_config[CONF_API_KEY] = api_key
        yield from _setup_deconz(hass, deconz_config)

    hass.services.async_register(DOMAIN, 'generate_api_key', generate_api_key)

    if CONF_API_KEY in deconz_config:
        yield from _setup_deconz(hass, deconz_config)
    else:
        _LOGGER.warning("Deconz lacking API key to set up session. See docs.")

    return True


@asyncio.coroutine
def _setup_deconz(hass, deconz_config):
    """
    """
    from .deconz_lib import DeconzSession
    print(deconz_config)
    DECONZ = DeconzSession(hass.loop, **deconz_config)
    result = yield from DECONZ.populate_config()
    result = yield from DECONZ.populate_sensors()
