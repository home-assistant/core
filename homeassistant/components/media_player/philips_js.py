"""
Media Player component to integrate TVs exposing the Joint Space API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.philips_js/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP, SUPPORT_PLAY, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN)
from homeassistant.util import Throttle

REQUIREMENTS = ['ha-philipsjs==0.0.1']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SUPPORT_PHILIPS_JS = SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE

SUPPORT_PHILIPS_JS_TV = SUPPORT_PHILIPS_JS | SUPPORT_NEXT_TRACK | \
                        SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_NAME = 'Philips TV'
BASE_URL = 'http://{0}:1925/1/{1}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Philips TV platform."""
    import haphilipsjs

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    tvapi = haphilipsjs.PhilipsTV(host)

    add_devices([PhilipsTV(tvapi, name)])


class PhilipsTV(MediaPlayerDevice):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name):
        """Initialize the Philips TV."""
        self._tv = tv
        self._name = name
        self._state = STATE_UNKNOWN
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._source = None
        self._source_list = []
        self._connfail = 0
        self._source_mapping = {}
        self._watching_tv = None
        self._channel_name = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._watching_tv:
            return SUPPORT_PHILIPS_JS_TV
        else:
            return SUPPORT_PHILIPS_JS

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        return self._state

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_mapping:
            self._tv.setSource(self._source_mapping.get(source))
            self._source = source
            if not self._tv.on:
                self._state = STATE_OFF
            self._watching_tv = bool(self._tv.source_id == 'tv')

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_off(self):
        """Turn off the device."""
        self._tv.sendKey('Standby')
        if not self._tv.on:
            self._state = STATE_OFF

    def volume_up(self):
        """Send volume up command."""
        self._tv.sendKey('VolumeUp')
        if not self._tv.on:
            self._state = STATE_OFF

    def volume_down(self):
        """Send volume down command."""
        self._tv.sendKey('VolumeDown')
        if not self._tv.on:
            self._state = STATE_OFF

    def mute_volume(self, mute):
        """Send mute command."""
        self._tv.sendKey('Mute')
        if not self._tv.on:
            self._state = STATE_OFF

    def media_previous_track(self):
        """Send rewind commmand."""
        self._tv.sendKey('Previous')

    def media_next_track(self):
        """Send fast forward commmand."""
        self._tv.sendKey('Next')

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._watching_tv:
            if self._channel_name:
                return '{} - {}'.format(self._source, self._channel_name)
            else:
                return self._source
        else:
            return self._source

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()
        self._min_volume = self._tv.min_volume
        self._max_volume = self._tv.max_volume
        self._volume = self._tv.volume
        self._muted = self._tv.muted
        if self._tv.source_id:
            src = self._tv.sources.get(self._tv.source_id, None)
            if src:
                self._source = src.get('name', None)
        if self._tv.sources and not self._source_list:
            for srcid in sorted(self._tv.sources):
                srcname = self._tv.sources.get(srcid, dict()).get('name', None)
                self._source_list.append(srcname)
                self._source_mapping[srcname] = srcid
        if self._tv.on:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        self._watching_tv = bool(self._tv.source_id == 'tv')

        self._tv.getChannelId()
        self._tv.getChannels()
        if self._tv.channels and self._tv.channel_id in self._tv.channels:
            self._channel_name = self._tv.channels[self._tv.channel_id]['name']
        else:
            self._channel_name = None
