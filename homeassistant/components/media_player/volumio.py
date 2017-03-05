"""Support for controlling a Volumia network audio device in Home Assistant."""
>>>>>>> parent of b792bc17... Add config to docstring
import logging
import json
import os
import time
import asyncio
import socketIO_client
import aiohttp
import async_timeout
import voluptuous

from homeassistant.components.media_player import (
SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_PLAY, SUPPORT_VOLUME_STEP, MediaPlayerDevice,
    PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC)
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF, STATE_IDLE, CONF_HOST, CONF_PORT, CONF_NAME, STATE_ON)
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession


_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Volumia'
DEFAULT_PORT = 3000
TIMEOUT      = 10

SUPPORT_VOLUMIA = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_PLAY


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    voluptuous.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    voluptuous.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    voluptuous.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})



@asyncio.coroutine
def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """ Setup the Volumia platform """
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    yield from add_entities([Volumia(name, host, port, hass)])

class Volumia(MediaPlayerDevice):
    """Volumia Player Object"""

    def __init__(self, name, host, port, hass):
        """Initialize the media player."""
        self.host = host
        self.port = port
        self.hass = hass
        self._url = host + ":" + str(port)
        self._name = name
        self._state = {}
        self.async_update()


    @asyncio.coroutine
    def send_volumia_msg(self, method, params=None):
        """Send message"""
        url = "http://{}:{}/api/v1/{}/".format(
            self.host, self.port, method)
        response = None

        _LOGGER.debug("URL: %s params: %s", url, params)

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(TIMEOUT, loop=self.hass.loop):
                response = yield from websession.get(
                    url,
                    params=params)
                if response.status == 200:
                    data = yield from response.json()
                else:
                    _LOGGER.error(
                        "Query failed, response code: %s Full message: %s",
                        response.status, response)
                    return False

        except (asyncio.TimeoutError,
                aiohttp.errors.ClientError,
                aiohttp.errors.ClientDisconnectedError) as error:
            _LOGGER.error("Failed communicating with Volumia: %s", type(error))
            return False
        finally:
            if response is not None:
                yield from response.release()

        try:
            return data
        except AttributeError:
            _LOGGER.error("Received invalid response: %s", data)
            return False
        
    @asyncio.coroutine
    def async_update(self):
        resp = yield from self.send_volumia_msg('getState')
        if resp is False:
            return
        self._state = resp.copy()

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC
    
    @property
    def state(self):
        """Return the state of the device."""
        status = self._state.get('status',None)
        if status == 'pause': return STATE_PAUSED
        elif status == 'play': return STATE_PLAYING
        else: return STATE_IDLE

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._state.get('title', None)
    
    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._state.get('artist',None)

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        return self._state.get('album',None)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        url = self._state.get('albumart',None)
        if url is None: return
        if str(url[0:2]).lower() == 'ht':
            mediaurl = url
        else:
            mediaurl = "http://" + self.host + ":" + str(self.port) + url
        return mediaurl

    @property
    def media_seek_position(self):
        """Time in seconds of current seek position."""
        return self._state.get('seek',None)

    @property
    def media_duration(self):
        """Time in seconds of current song duration."""
        return self._state.get('duration',None)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        vol = self._state.get('volume',None)
        if vol is not None: vol=vol/100
        return vol
    
    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_VOLUMIA

    def async_media_next_track(self):
        """Send media_next command to media player."""
        return self.send_volumia_msg('commands',params={'cmd':'next'})

    def async_media_previous_track(self):
        """Send media_previous command to media player."""
        return self.send_volumia_msg('commands',paams={'cmd':'prev'})

    def async_media_play(self):
        """Send media_play command to media player."""
        return self.send_volumia_msg('commands',params={'cmd':'play'})
        
    def async_media_pause(self):
        """Send media_pause command to media player."""
        return self.send_volumia_msg('commands',params={'cmd':'pause'})

    def async_set_volume_level(self, volume):
        """Send volume_up command to media player."""
        return self.send_volumia_msg('commands',params={'cmd':'volume','volume':int(volume*100)})

    def async_mute_volume(self):
        """Send volume_up command to media player."""
        mutecmd = 'unmute' if self._state['mute'] else 'mute'
        return self.send_volumia_msg('commands',params={'cmd':'volume','volume':mutecmd})
