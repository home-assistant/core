"""Media Player component to integrate TVs exposing the Joint Space API."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,
    MEDIA_TYPE_CHANNEL)
from homeassistant.const import (
    CONF_API_VERSION, CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_PHILIPS_JS = SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                     SUPPORT_SELECT_SOURCE | SUPPORT_NEXT_TRACK | \
                     SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY_MEDIA

CONF_ON_ACTION = 'turn_on_action'

DEFAULT_NAME = "Philips TV"
DEFAULT_API_VERSION = '1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): cv.string,
    vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
})


def _inverted(data):
    return {v: k for k, v in data.items()}

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
        self._sources = {}
        self._channels = {}
        self._on_script = on_script
        self._supports = SUPPORT_PHILIPS_JS
        if self._on_script:
            self._supports |= SUPPORT_TURN_ON

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
        return self._supports

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        if self._tv.on:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def source(self):
        """Return the current input source."""
        return self._sources.get(self._tv.source_id)

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sources.values())

    def select_source(self, source):
        """Set the input source."""
        source_id = _inverted(self._sources).get(source)
        if source_id:
            self._tv.setSource(source_id)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._tv.volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._tv.muted

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
        self._tv.setVolume(self._tv.volume, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._tv.setVolume(volume, self._tv.muted)

    def media_previous_track(self):
        """Send rewind command."""
        self._tv.sendKey('Previous')

    def media_next_track(self):
        """Send fast forward command."""
        self._tv.sendKey('Next')

    @property
    def media_channel(self):
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        else:
            return None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        else:
            return self._sources.get(self._tv.source_id)

    @property
    def media_content_type(self):
        """Return content type of playing media"""
        if (self._tv.source_id == 'tv' or self._tv.source_id == '11'):
            return MEDIA_TYPE_CHANNEL
        else:
            return None

    @property
    def media_content_id(self):
        """Content type of current playing media."""
        if self.media_content_type == MEDIA_TYPE_CHANNEL:
            return self._channels.get(self._tv.channel_id)
        else:
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'channel_list': list(self._channels.values())
        }


    def update(self):
        """Get the latest data and update device state."""
        self._tv.update()
        self._tv.getChannelId()
        self._tv.getChannels()

        self._sources = {
            srcid: source['name'] or "Source {}".format(srcid)
            for srcid, source in (self._tv.sources or {}).items()
        }

        self._channels = {
            chid: channel['name']
            for chid, channel in (self._tv.channels or {}).items()
        }
