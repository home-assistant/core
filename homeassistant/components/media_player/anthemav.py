"""
Support for Anthem Network Receivers and Processors

"""
import logging
import asyncio
import voluptuous as vol

DOMAIN = 'anthemav'

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNKNOWN,
    EVENT_HOMEASSISTANT_STOP, CONF_SCAN_INTERVAL)
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['anthemav']

DEFAULT_NAME = "Anthem AVR"

SUPPORT_ANTHEMAV = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))
    })

SCAN_INTERVAL = 120

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):

    import anthemav

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    SCAN_INTERVAL = config.get(CONF_SCAN_INTERVAL) or 120

    _LOGGER.info('Provisioning Anthem AVR device at '+host+':'+str(port)+' with a '+str(SCAN_INTERVAL)+' second scan interval')

    device = AnthemAVR(hass,host,port)

    yield from async_add_devices([device])

    def anthemav_update_callback(message):
        _LOGGER.info("Received update callback from AVR: %s" % message)
        hass.async_add_job(device.async_update_ha_state)

    avr =  yield from anthemav.Connection.create(host=host,port=port,loop=hass.loop,update_callback=anthemav_update_callback)
    device._avr = avr

    _LOGGER.warn('dump_devicedata: '+device.dump_avrdata)
    _LOGGER.warn('dump_conndata: '+avr.dump_conndata)
    _LOGGER.warn('dump_rawdata: '+avr.protocol.dump_rawdata)

    #transport, _ = yield from hass.loop.create_task(avr)
    #hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, transport.close)

class AnthemAVR(MediaPlayerDevice):
    def __init__(self,hass,host,port):
        super().__init__()
        self.hass = hass
        self._host = host
        self._port = port

    def poll_and_return(self,property,dval):
        if self.reader:
            pval = getattr(self.reader, property)
            _LOGGER.debug('query for '+property+' returned from avr object: '+str(pval))
            return pval
        else:
            _LOGGER.debug('query for '+property+' returned from fallback: '+str(dval))
            return dval

    def poll_or_null(self,property):
        if self.reader:
            pval = getattr(self.reader, property)
            _LOGGER.debug('query for '+property+' returned from avr object: '+str(pval))
            return pval
        else:
            return 

    @property
    def reader(self):
        if hasattr(self, '_avr'):
            if hasattr(self._avr, 'protocol'):
                return self._avr.protocol

    @reader.setter
    def reader(self,value):
        self._reader = value

    @property
    def supported_media_commands(self):
        return SUPPORT_ANTHEMAV

    @property
    def name(self):
        return self.poll_and_return('model',DEFAULT_NAME)

    @property
    def state(self):
        pwrstate = self.poll_or_null('power')

        if pwrstate == True:
            return STATE_ON
        elif pwrstate == False:
            return STATE_OFF
        else:
            return STATE_UNKNOWN

    @property
    def volume_level(self):
        return self.poll_and_return('volume_as_percentage',0.0)

    @property
    def media_title(self):
        return self.poll_and_return('input_name','No Source')

    @property
    def app_name(self):
        return self.poll_and_return('video_input_resolution_text','')+' '+self.poll_and_return('audio_input_name','')

    @property
    def source(self):
        return self.poll_and_return('input_name',"Unknown")

    @property
    def source_list(self):
        return self.poll_and_return('input_list',["Unknown"])

    def media_play(self):
        return

    def select_source(self, source):
        self.update_avr('input_name',source)

    def turn_off(self):
        self.update_avr('power',False)

    def turn_on(self):
        self.update_avr('power',True)

    def volume_up(self):
        _LOGGER.debug('volume up')

    def volume_down(self):
        _LOGGER.debug('volume down')

    def set_volume_level(self, volume):
        self.update_avr('volume_as_percentage',volume)
        
    def mute_volume(self, mute):
        _LOGGER.debug('Request to mute %s',str(mute))

    def update_avr(self,property,value):
        _LOGGER.info('Sending command to AVR: set '+property+' to '+str(value))
        if hasattr(self, 'reader'):
            setattr(self.reader, property,value)
        else:
            _LOGGER.warn('Unable to issue command to missing AVR')

    @asyncio.coroutine
    def async_update(self):
        _LOGGER.info('async_update invoked')
        _LOGGER.warn(self.dump_avrdata)

    @property
    def dump_avrdata(self):
        attrs = vars(self)
        return('dump_avrdata: '+', '.join("%s: %s" % item for item in attrs.items()))
