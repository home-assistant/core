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
    _LOGGER.info('Provisioning Anthem AVR device at '+host+':'+str(port))

    device = AnthemAVR(hass,host,port)

    yield from async_add_devices([device])

    def update_entities_message(connobj,message):
        _LOGGER.info('update_entities_message'+message)
        device.reader = connobj
        hass.async_add_job(device.async_update_ha_state)

    avr = create_anthemav_reader(host,port,update_entities_message, loop=hass.loop)

    transport, _ = yield from hass.loop.create_task(avr)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, transport.close)

class AnthemAVR(MediaPlayerDevice):
    def __init__(self,hass,host,port):
        super().__init__()
        self.hass = hass
        self._host = host
        self._port = port

    def poll_and_return(self,property,dval):
        _LOGGER.debug('p&r for '+property)
        if self.reader:
            _LOGGER.debug('reader exists, should I risk it?')
            pval = getattr(self.reader, property)
            _LOGGER.debug('And here it is: '+str(pval))
            return pval
        else:
            _LOGGER.debug('Punting and sending: '+str(dval))
            return dval

    @property
    def reader(self):
        if hasattr(self, '_reader'):
            return self._reader
        else:
            return

    @reader.setter
    def reader(self,value):
        self._reader = value

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
    def volume_level(self):
        _LOGGER.debug('query for volume')
        self.poll_and_return('volume_as_percentage',0.0)

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

    def volume_down(self):
        _LOGGER.debug('volume down')


    def set_volume_level(self, volume):
        _LOGGER.debug('Request to set volume to %f',volume)
        
    def mute_volume(self, mute):
        _LOGGER.debug('Request to mute %s',str(mute))

    @asyncio.coroutine
    def async_update(self):
        _LOGGER.info('async_update invoked')
        if self.reader:
            _LOGGER.warn(self.reader.staticstring)

