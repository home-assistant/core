"""
Support for Anthem Network Receivers and Processors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.anthemav/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNKNOWN,
    EVENT_HOMEASSISTANT_STOP, CONF_SCAN_INTERVAL)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['anthemav==1.1.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'anthemav'

DEFAULT_NAME = "Anthem AVR"

SUPPORT_ANTHEMAV = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    })

SCAN_INTERVAL = 120


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up our socket to the AVR."""
    import anthemav

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    _LOGGER.info('Provisioning Anthem AVR device at %s:%d scan every %d sec',
                 host, port, SCAN_INTERVAL)

    device = AnthemAVR(hass, host, port)

    yield from async_add_devices([device])

    def anthemav_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update callback from AVR: %s', message)
        hass.async_add_job(device.async_update_ha_state)

    avr = yield from anthemav.Connection.create(
        host=host, port=port, loop=hass.loop,
        update_callback=anthemav_update_callback)

    device.avr = avr

    _LOGGER.debug('dump_devicedata: '+device.dump_avrdata)
    _LOGGER.debug('dump_conndata: '+avr.dump_conndata)
    _LOGGER.debug('dump_rawdata: '+avr.protocol.dump_rawdata)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.avr.close)


class AnthemAVR(MediaPlayerDevice):
    """Entity reading values from Anthem AVR protocol."""

    def __init__(self, hass, host, port):
        """"Initialize entity with hass, host, and port."""
        super().__init__()
        self.hass = hass
        self._host = host
        self._port = port
        self.avr = None

    def _poll_and_return(self, propname, dval):
        if self.reader:
            pval = getattr(self.reader, propname)
            _LOGGER.debug('query '+propname+' returned from avr: '+str(pval))
            return pval
        else:
            _LOGGER.debug('query '+propname+' returned default: '+str(dval))
            return dval

    def _poll_or_null(self, propname):
        if self.reader:
            pval = getattr(self.reader, propname)
            _LOGGER.debug('query '+propname+' returned from avr: '+str(pval))
            return pval
        else:
            return

    @property
    def reader(self):
        """Expose the protocol with smart wrapper."""
        if hasattr(self, 'avr'):
            if hasattr(self.avr, 'protocol'):
                return self.avr.protocol

    @reader.setter
    def reader(self, value):
        self.avr.protocol = value

    @property
    def supported_media_commands(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_ANTHEMAV

    @property
    def name(self):
        """Return name of device."""
        return self._poll_and_return('model', DEFAULT_NAME)

    @property
    def state(self):
        """Return state of power on/off."""
        pwrstate = self._poll_or_null('power')

        if pwrstate is True:
            return STATE_ON
        elif pwrstate is False:
            return STATE_OFF
        else:
            return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Return volume level from 0 to 1."""
        return self._poll_and_return('volume_as_percentage', 0.0)

    @property
    def media_title(self):
        """Return current input name (closest we have to media title)."""
        return self._poll_and_return('input_name', 'No Source')

    @property
    def app_name(self):
        """Return details about current video and audio stream."""
        return self._poll_and_return('video_input_resolution_text', '') + ' ' \
            + self._poll_and_return('audio_input_name', '')

    @property
    def source(self):
        """Return currently selected input."""
        return self._poll_and_return('input_name', "Unknown")

    @property
    def source_list(self):
        """Return all active, configured inputs."""
        return self._poll_and_return('input_list', ["Unknown"])

    def media_play(self):
        """Unsupported."""
        return

    def select_source(self, source):
        """Change AVR to the designated source (by name)."""
        self.update_avr('input_name', source)

    def turn_off(self):
        """Turn AVR power off."""
        self.update_avr('power', False)

    def turn_on(self):
        """Turn AVR power on."""
        self.update_avr('power', True)

    def volume_up(self):
        """Unsupported."""
        _LOGGER.debug('volume up')

    def volume_down(self):
        """Unsupported."""
        _LOGGER.debug('volume down')

    def set_volume_level(self, volume):
        """Set AVR volume (0 to 1)."""
        self.update_avr('volume_as_percentage', volume)

    def mute_volume(self, mute):
        """Engage AVR mute."""
        _LOGGER.debug('Request to mute %s', str(mute))

    def update_avr(self, propname, value):
        """Update a property in the AVR."""
        _LOGGER.info('Sending command to AVR: set '+propname+' to '+str(value))
        if hasattr(self, 'reader'):
            setattr(self.reader, propname, value)
        else:
            _LOGGER.warning('Unable to issue command to missing AVR')

    @asyncio.coroutine
    def async_update(self):
        """Vestigial function unneeeded because this platform is local push."""
        _LOGGER.info('async_update invoked')
        _LOGGER.debug(self.dump_avrdata)

    @property
    def dump_avrdata(self):
        """Return state of avr object for debugging forensics."""
        attrs = vars(self)
        return(
            'dump_avrdata: '
            + ', '.join('%s: %s' % item for item in attrs.items()))
