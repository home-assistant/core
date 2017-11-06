"""Platform integrating Deconz support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""

import asyncio
import logging
import voluptuous as vol

from homeassistant.const import (CONF_API_KEY, CONF_HOST, CONF_PASSWORD,
                                 CONF_PORT, CONF_USERNAME,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['pydeconz==2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'deconz'

DECONZ = None
DATA_DECONZ = 'data_deconz'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_USERNAME, default='delight'): cv.string,
        vol.Optional(CONF_PASSWORD, default='delight'): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup services for Deconz."""
    deconz_config = config[DOMAIN]

    @callback
    def _shutdown(call):  # pylint: disable=unused-argument
        """Stop the connections to Deconz on shutdown."""
        if DATA_DECONZ in hass.data:
            _LOGGER.info("Stopping Deconz session.")
            hass.data[DATA_DECONZ].close()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    @asyncio.coroutine
    def generate_api_key(call):
        """Generate API key needed to communicate with Deconz."""
        from pydeconz.utils import get_api_key
        api_key = yield from get_api_key(**deconz_config)
        hass.states.async_set('deconz.api_key', api_key)
        deconz_config[CONF_API_KEY] = api_key
        yield from _setup_deconz(hass, config, deconz_config)

    if CONF_API_KEY in deconz_config:
        yield from _setup_deconz(hass, config, deconz_config)
    else:
        hass.services.async_register(
            DOMAIN, 'generate_api_key', generate_api_key)
        _LOGGER.warning("Deconz lacking API key to set up session. See docs.")

    return True


@asyncio.coroutine
def _setup_deconz(hass, config, deconz_config):
    """Setup Deconz session.

    Load config data for server information.
    Load light data to know which lights are available.
    Load sensor data to know which sensors are available.
    Start websocket for push notification of state changes from Deconz.
    """
    from pydeconz import DeconzSession
    DECONZ = DeconzSession(hass.loop, **deconz_config)
    hass.data[DATA_DECONZ] = DECONZ
    yield from DECONZ.populate_config()
    yield from DECONZ.populate_lights()
    yield from DECONZ.populate_sensors()
    hass.async_add_job(discovery.async_load_platform(hass,
                                                     'light',
                                                     DOMAIN,
                                                     {},
                                                     config))
    hass.async_add_job(discovery.async_load_platform(hass,
                                                     'binary_sensor',
                                                     DOMAIN,
                                                     {},
                                                     config))
    hass.async_add_job(discovery.async_load_platform(hass,
                                                     'sensor',
                                                     DOMAIN,
                                                     {},
                                                     config))
    DECONZ.start()
