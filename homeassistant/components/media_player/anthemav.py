"""
Support for Anthem Network Receivers and Processors

"""
import logging
import asyncio
import voluptuous as vol

import anthemav

DOMAIN = 'anthemav'

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNKNOWN,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv

from anthemav.protocol import create_anthemav_reader

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Anthem AVR"

SUPPORT_ANTHEMAV = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    })

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    yield from async_add_devices([AnthemAVR(hass,host,port)], True)

    def update_entities_message(message):
        _LOGGER.info('update_entities_message'+message)

    # conn = create_anthemav_reader(args.host,args.port,print_callback,loop=loop)
    avr = create_anthemav_reader(host,port,update_entities_message, loop=hass.loop)
    transport, _ = yield from hass.loop.create_task(avr)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, transport.close)

class AnthemAVR(MediaPlayerDevice):
    def __init__(self,hass,host,port):
        super().__init__()
        self.hass = hass
        self._host = host
        self._port = port

    @property
    def supported_media_commands(self):
        _LOGGER.debug('query for supported media commands')
        return SUPPORT_ANTHEMAV

    @property
    def name(self):
        _LOGGER.debug('query for name')
        return "Anthem AVR"

    @property
    def state(self):
        _LOGGER.debug('query for state')
        return STATE_ON

    @property
    def media_title(self):
        return "Media Title"

    @property
    def app_name(self):
        return "App Name"

    @property
    def source(self):
        return "Source"

    @property
    def source_list(self):
        return ['Source', 'Moo', 'Cow']

    def media_play(self):
        return

    def select_source(self, source):
        _LOGGER.debug('Select %s',source)

    def turn_off(self):
        _LOGGER.debug('turn me off')

    def turn_on(self):
        _LOGGER.debug('turn me on')

    def volume_up(self):
        _LOGGER.debug('volume up')
        return 0.5

    def volume_down(self):
        _LOGGER.debug('volume down')

    def set_volume_level(self, volume):
        _LOGGER.debug('Request to set volume to %f',volume)
        
    def mute_volume(self, mute):
        _LOGGER.debug('Request to mute %s',str(mute))

    def update(self):
        _LOGGER.info('update invoked')
        return run_coroutine_threadsafe(self.async_update(), self.hass.loop).result()

    @asyncio.coroutine
    def async_update(self):
        _LOGGER.info('async_update invoked')

