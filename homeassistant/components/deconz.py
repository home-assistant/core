"""
Support for deCONZ support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/deconz/
"""

import asyncio
import os
import logging
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_API_KEY, CONF_EVENT, CONF_HOST, CONF_ID, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback, EventOrigin
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util import slugify
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pydeconz==18']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'deconz'

DECONZ_DATA = 'deconz_data'
CONFIG_FILE = 'deconz.conf'

CONF_SWITCH_AS_EVENT = 'switch_as_event'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_SWITCH_AS_EVENT, default=True): cv.boolean,
        vol.Optional(CONF_USERNAME, default='delight'): cv.string,
        vol.Optional(CONF_PASSWORD, default='delight'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_FW_VERSION = 'firmware_version'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_MODEL_ID = 'model_number'
ATTR_UNIQUE_ID = 'uniqueid'


@asyncio.coroutine
def async_setup(hass, config):
    """Setup services for Deconz."""
    deconz_config = config[DOMAIN]
    config_file = load_json(hass.config.path(CONFIG_FILE))
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]

    @callback
    def _shutdown(call):  # pylint: disable=unused-argument
        """Stop the connections to Deconz on shutdown."""
        if DECONZ_DATA in hass.data:
            _LOGGER.info("Stopping Deconz session.")
            hass.data[DECONZ_DATA].close()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    @asyncio.coroutine
    def _configure(call):
        """Set attribute of device in Deconz.

        Field is a string representing a specific device in Deconz
        e.g. field='/lights/1/state'.
        Data is a json object with what data you want to alter
        e.g. data={'on': true}.
        {
            "field": "/lights/1/state",
            "data": {"on": true}
        }
        See Dresden Elektroniks REST API documentation for details:
        http://dresden-elektronik.github.io/deconz-rest-doc/rest/
        """
        deconz = hass.data[DECONZ_DATA]
        field = call.data.get('field')
        data = call.data.get('data')
        yield from deconz.put_state_async(field, data)
    hass.services.async_register(
        DOMAIN, 'configure', _configure, descriptions['configure'])

    if CONF_API_KEY in deconz_config:
        pass
    elif CONF_API_KEY in config_file:
        deconz_config[CONF_API_KEY] = config_file[CONF_API_KEY]
    else:
        from pydeconz.utils import get_api_key
        api_key = yield from get_api_key(hass.loop, **deconz_config)
        deconz_config[CONF_API_KEY] = api_key
        if not save_json(
                hass.config.path(CONFIG_FILE), {CONF_API_KEY: api_key}):
            _LOGGER.error("Failed to save API key to %s", CONFIG_FILE)
    result = yield from _setup_deconz(hass, config, deconz_config)
    return result is not False


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
    result = yield from deconz.load_parameters()
    if result is False:
        _LOGGER.error('Failed to setup deCONZ component')
        return False
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
                                                     'scene',
                                                     DOMAIN,
                                                     {},
                                                     config))
    hass.async_add_job(discovery.async_load_platform(hass,
                                                     'sensor',
                                                     DOMAIN,
                                                     deconz_config,
                                                     config))
    deconz.start()
    return True


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
        self._event = DOMAIN + '_' + CONF_EVENT
        self._id = slugify(self._device.name)

    @callback
    def _update_callback(self, reason):
        """Fire the event if reason is that state is updated."""
        if reason['state']:
            data = {CONF_ID: self._id, CONF_EVENT: self._device.state}
            self._hass.bus.async_fire(self._event, data, EventOrigin.remote)
