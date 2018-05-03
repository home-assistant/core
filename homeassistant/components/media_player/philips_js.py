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
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,
    SUPPORT_PLAY, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_API_VERSION, STATE_OFF, STATE_ON, STATE_UNKNOWN)
from homeassistant.helpers.script import Script
from homeassistant.util import Throttle

REQUIREMENTS = ['ha-philipsjs==0.0.4']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SUPPORT_PHILIPS_JS = SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                     SUPPORT_SELECT_SOURCE

SUPPORT_PHILIPS_JS_V5 = SUPPORT_PHILIPS_JS | SUPPORT_VOLUME_SET

SUPPORT_PHILIPS_JS_TV = SUPPORT_PHILIPS_JS | SUPPORT_NEXT_TRACK | \
                        SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

CONF_ON_ACTION = 'turn_on_action'

DEFAULT_DEVICE = 'default'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_NAME = 'Philips TV'
DEFAULT_API_VERSION = '1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): cv.string,
    vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Philips TV platform."""
    import haphilipsjs

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    api_version = config.get(CONF_API_VERSION)
    turn_on_action = config.get(CONF_ON_ACTION)

    tvapi = haphilipsjs.PhilipsTV(host, api_version)
    on_script = Script(hass, turn_on_action) if turn_on_action else None

    add_devices([PhilipsTV(tvapi, name, on_script)])


class PhilipsTV(MediaPlayerDevice):
    """Representation of a Philips TV exposing the JointSpace API."""

    def __init__(self, tv, name, on_script):
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
        if self._tv._api_version == '5':
            return SUPPORT_PHILIPS_JS_V5 | is_supporting_turn_on
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

    def _select_body(self, ccid):
        return {"channelList": {"id": "alltv"}, "channel": {"ccid": ccid}}

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_mapping:
            id = self._source_mapping.get(source)
            if self._tv._api_version == '5':
                self._tv._postReq('activities/tv', self._select_body(id))
            else:
                self._tv.setSource(id)
            self._source = source
            if not self._tv.on:
                self._state = STATE_OFF
            if self._tv._api_version != '5':
                self._watching_tv = bool(self._tv.source_id == 'tv')

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self._volume != volume:
            self._setVolume(volume)
            self._volume = volume
            if not self._tv.on:
                self._state = STATE_OFF

    def _setVolume(self, level):
        if level:
            if self._min_volume != 0 or not self._max_volume:
                self.getAudiodata()
            try:
                targetlevel = int(level * self._max_volume)
            except ValueError:
                _LOGGER.warning("Invalid audio level %s" % str(level))
                return
            body = {'current': targetlevel, 'muted': False}
            self._tv._postReq('audio/volume', body)

    def turn_on(self):
        """Turn on the device."""
        if self._on_script:
            self._on_script.run()

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

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self._volume != volume:
            self._tv.setVolume(volume)
            if not self._tv.on:
                self._state = STATE_OFF

    def media_previous_track(self):
        """Send rewind command."""
        self._tv.sendKey('Previous')

    def media_next_track(self):
        """Send fast forward command."""
        self._tv.sendKey('Next')

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._tv._api_version == '5':
            return self._source
        if self._watching_tv and self._channel_name:
            return '{} - {}'.format(self._source, self._channel_name)
        return self._source

    def _update_sources_v1(self):
        if self._tv.source_id:
            self._source = self._tv.getSourceName(self._tv.source_id)
        if self._tv.sources and not self._source_list:
            for srcid in self._tv.sources:
                srcname = self._tv.getSourceName(srcid)
                self._source_list.append(srcname)
                self._source_mapping[srcname] = srcid
        self._watching_tv = bool(self._tv.source_id == 'tv')
        self._tv.getChannelId()
        self._tv.getChannels()
        if self._tv.channels and self._tv.channel_id in self._tv.channels:
            self._channel_name = self._tv.channels[self._tv.channel_id]['name']
        else:
            self._channel_name = None

    def _update_sources_v5(self):
        r = self._tv._getReq('channeldb/tv/channelLists/alltv')
        if r:
            self._channels = r['Channel']
        r = self._tv._getReq('activities/tv')
        if r:
            self._channel_name = r['channel']['name']
            self._source = r['channel']['name']

        if self._channels and not self._source_list:
            for channel in self._channels:
                srcname = channel['name']
                self._source_list.append(srcname)
                self._source_mapping[srcname] = channel['ccid']

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and update device state."""
        if self._tv._api_version == '5':
            self._tv.getName()
            self._tv.getAudiodata()
            self._volume = self._tv.volume / self._tv.max_volume
            self._update_sources_v5()
        else:
            self._tv.update()
            self._volume = self._tv.volume
            self._update_sources_v1()
        self._min_volume = self._tv.min_volume
        self._max_volume = self._tv.max_volume
        self._muted = self._tv.muted
        if self._tv.on:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF
