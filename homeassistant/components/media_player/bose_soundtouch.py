"""
Support for interface with a Bose SoundTouch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.bose_soundtouch/
"""
import logging
import os
import json
import re

import voluptuous as vol

from homeassistant.loader import get_component
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    MEDIA_TYPE_MUSIC, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, 
    STATE_IDLE, STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

#REQUIREMENTS = ['boos==0.5.1']
REQUIREMENTS = ['https://github.com/trunet/boos'
                '/archive/master.zip'
                '#boos==0.5.1']

DEFAULT_NAME = 'Bose SoundTouch'

_LOGGER = logging.getLogger(__name__)
_REQUESTS_LOGGER = logging.getLogger('requests')
_REQUESTS_LOGGER.setLevel(logging.ERROR)

SUPPORT_BOSE_SOUNDTOUCH = SUPPORT_PAUSE | \
                 SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_SELECT_SOURCE | \
                 SUPPORT_VOLUME_STEP | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
                 SUPPORT_PAUSE | SUPPORT_PLAY_MEDIA | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Bose SoundTouch device."""
    from boos import Boos
    if discovery_info:
        client = Boos("http://{host}:{port}".format(host=discovery_info[0], port=discovery_info[1]))
        bose_soundtouch = BoseSoundTouch(client)
        add_devices([bose_soundtouch])
        return True
    

# pylint: disable=abstract-method, too-many-public-methods,
# pylint: disable=too-many-instance-attributes, too-many-arguments
class BoseSoundTouch(MediaPlayerDevice):
    """ Representation of Bose SoundTouch device."""

    def __init__(self, client):
        self._client = client
        self._name = ''
        self._state = 'STANDBY'
        self._source = None
        self._now_playing = None
        self._volume = 0
        self._muted = False
        self.update()

    def update(self):
        self._state = self._client.state()
        if self._state == 'AUX':
            self._source == 'AUX'
        self._now_playing = self._client.now_playing()
        self._volume = (float(self._client.vol()) / 100.0)
        self._muted = self._client.muted()
        self._name = self._client.name()

    @property
    def supported_media_commands(self):
        return SUPPORT_BOSE_SOUNDTOUCH

    @property
    def media_content_type(self):
        return MEDIA_TYPE_MUSIC

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        presets = ['AUX']
        for preset_id, preset_title in self._client.presets().items():
            presets.append('{id} - {title}'.format(id=preset_id, title=preset_title))
        return presets

    @property
    def state(self):
        if self._state == 'STANDBY':
            return STATE_OFF
        else:
            return STATE_ON

    @property
    def name(self):
        return self._name

    @property
    def volume_level(self):
        return self._volume

    @property
    def is_volume_muted(self):
        return self._muted

    @property
    def media_title(self):
        return self._now_playing

    def select_source(self, source):
        self._source = source
        if source == 'AUX':
            self._client.aux()
        else:
            preset = source.split(' - ')
            self._client.preset(preset[0])

    def media_next_track(self):
        self._client.next()

    def media_previous_track(self):
        self._client.prev()

    def media_play(self):
        self._client.play()

    def media_pause(self):
        self._client.pause()

    def turn_off(self):
        if self._state != 'STANDBY':
            self._client.power()

    def turn_on(self):
        if self._state == 'STANDBY':
            self._client.power()

    def mute_volume(self, mute):
        self._client.mute()
        self.update()

    def volume_up(self):
        self._client.volup()
        self.update()

    def volume_down(self):
        self._client.voldown()
        self.update()

    def set_volume_level(self, volume):
        self._client.vol(volume * 100)
        self.update()
