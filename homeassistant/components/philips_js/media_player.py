"""Media Player component to integrate TVs exposing the Joint Space API."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP)
from homeassistant.const import (
    CONF_API_VERSION, CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_PHILIPS_JS = SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                     SUPPORT_SELECT_SOURCE

SUPPORT_PHILIPS_JS_TV = SUPPORT_PHILIPS_JS | SUPPORT_NEXT_TRACK | \
                        SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

CONF_ON_ACTION = 'turn_on_action'

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_NAME = "Philips TV"
DEFAULT_API_VERSION = '1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): cv.string,
    vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Philips TV platform."""
    import haphilipsjs

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    api_version = config.get(CONF_API_VERSION)
    turn_on_action = config.get(CONF_ON_ACTION)

    tvapi = haphilipsjs.PhilipsTV(host, api_version)
    on_script = Script(hass, turn_on_action) if turn_on_action else None

    add_entities([PhilipsTV(tvapi, name, on_script)])


class PhilipsTV(MediaPlayerDevice):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name, on_script):
        """Initialize the Philips TV."""
        self._tv = tv
        self._name = name
        self._state = None
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
        self._on_script = on_script

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
        is_supporting_turn_on = SUPPORT_TURN_ON if self._on_script else 0
        if self._watching_tv:
            return SUPPORT_PHILIPS_JS_TV | is_supporting_turn_on
        return SUPPORT_PHILIPS_JS | is_supporting_turn_on

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

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_on(self):
        """Turn on the device."""
        if self._on_script:
            self._on_script.run()

    def turn_off(self):
        """Turn off the device."""
        self._tv.sendKey('Standby')

    def volume_up(self):
        """Send volume up command."""
        self._tv.sendKey('VolumeUp')

    def volume_down(self):
        """Send volume down command."""
        self._tv.sendKey('VolumeDown')

    def mute_volume(self, mute):
        """Send mute command."""
        if self._muted != mute:
            self._tv.sendKey('Mute')
            self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._tv.setVolume(volume)

    def media_previous_track(self):
        """Send rewind command."""
        self._tv.sendKey('Previous')

    def media_next_track(self):
        """Send fast forward command."""
        self._tv.sendKey('Next')

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._watching_tv and self._channel_name:
            return '{} - {}'.format(self._source, self._channel_name)
        return self._source

    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()
        self._volume = self._tv.volume
        self._muted = self._tv.muted
        if self._tv.source_id:
            self._source = self._tv.getSourceName(self._tv.source_id)
        if self._tv.sources and not self._source_list:
            for srcid in self._tv.sources:
                srcname = self._tv.getSourceName(srcid)
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
