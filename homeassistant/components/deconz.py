"""Platform integrating Deconz support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""

import asyncio
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback, EventOrigin
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util import slugify
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pydeconz==11']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'deconz'

DECONZ_DATA = 'deconz_data'
CONFIG_FILE = 'deconz.conf'

CONF_TYPE_AS_EVENT = 'type_as_event'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_TYPE_AS_EVENT, default=['ZHASwitch']):
            vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup services for Deconz."""
    deconz_config = config[DOMAIN]
    config_file = load_json(hass.config.path(CONFIG_FILE))

    @callback
    def _shutdown(call):  # pylint: disable=unused-argument
        """Stop the connections to Deconz on shutdown."""
        if DECONZ_DATA in hass.data:
            _LOGGER.info("Stopping Deconz session.")
            hass.data[DECONZ_DATA].close()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    @asyncio.coroutine
    def generate_api_key(call):
        """Generate API key needed to communicate with Deconz.

        Store API key in deconz.conf.
        """
        from pydeconz.utils import get_api_key
        deconz_config[CONF_USERNAME] = call.data.get(CONF_USERNAME, 'delight')
        deconz_config[CONF_PASSWORD] = call.data.get(CONF_PASSWORD, 'delight')
        api_key = yield from get_api_key(hass.loop, **deconz_config)
        if not save_json(
                hass.config.path(CONFIG_FILE), {CONF_API_KEY: api_key}):
            _LOGGER.error("Failed to save API key to %s", CONFIG_FILE)
        deconz_config[CONF_API_KEY] = api_key
        yield from _setup_deconz(hass, config, deconz_config)

    if CONF_API_KEY in deconz_config:
        yield from _setup_deconz(hass, config, deconz_config)
    elif CONF_API_KEY in config_file:
        deconz_config[CONF_API_KEY] = config_file[CONF_API_KEY]
        yield from _setup_deconz(hass, config, deconz_config)
    else:
        hass.services.async_register(
            DOMAIN, 'generate_api_key', generate_api_key)
        _LOGGER.warning("Deconz needs API key to set up session. See docs.")

    return True


@asyncio.coroutine
def _setup_deconz(hass, config, deconz_config):
    """Setup Deconz session.

    Load config data for server information.
    Load group data containing which light groups are available.
    Load light data containing which lights are available.
    Load sensor data containing which sensors are available.
    Start websocket for push notification of state changes from Deconz.
    """
    from pydeconz import DeconzSession
    deconz = DeconzSession(hass.loop, **deconz_config)
    hass.data[DECONZ_DATA] = deconz
    yield from deconz.populate_config()
    yield from deconz.populate_groups()
    yield from deconz.populate_lights()
    yield from deconz.populate_sensors()
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
                                                     deconz_config,
                                                     config))
    deconz.start()


class DeconzEvent(object):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, device):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._device = device
        self._device.register_callback(self._update_callback)
        self._event = 'deconz_event'
        self._id = slugify(self._device.name)

    @callback
    def _update_callback(self):
        """Fire the event."""
        data = {'id': self._id, 'event': self._device.state}
        self._hass.bus.async_fire(self._event, data, EventOrigin.remote)
