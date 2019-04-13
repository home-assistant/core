"""DuneHD implementation of the media player."""
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = 'DuneHD'

CONF_SOURCES = 'sources'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SOURCES): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

DUNEHD_PLAYER_SUPPORT = \
    SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_SELECT_SOURCE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DuneHD media player platform."""
    from pdunehd import DuneHDPlayer

    sources = config.get(CONF_SOURCES, {})
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    add_entities([DuneHDPlayerEntity(DuneHDPlayer(host), name, sources)], True)


class DuneHDPlayerEntity(MediaPlayerDevice):
    """Implementation of the Dune HD player."""

    def __init__(self, player, name, sources):
        """Initialize entity to control Dune HD."""
        self._player = player
        self._name = name
        self._sources = sources
        self._media_title = None
        self._state = None

    def update(self):
        """Update internal status of the entity."""
        self._state = self._player.update_state()
        self.__update_title()
        return True

    @property
    def state(self):
        """Return player state."""
        state = STATE_OFF
        if 'playback_position' in self._state:
            state = STATE_PLAYING
        if self._state['player_state'] in ('playing', 'buffering'):
            state = STATE_PLAYING
        if int(self._state.get('playback_speed', 1234)) == 0:
            state = STATE_PAUSED
        if self._state['player_state'] == 'navigator':
            state = STATE_ON
        return state

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return int(self._state.get('playback_volume', 0)) / 100

    @property
    def is_volume_muted(self):
        """Return a boolean if volume is currently muted."""
        return int(self._state.get('playback_mute', 0)) == 1

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return list(self._sources.keys())

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return DUNEHD_PLAYER_SUPPORT

    def volume_up(self):
        """Volume up media player."""
        self._state = self._player.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._state = self._player.volume_down()

    def mute_volume(self, mute):
        """Mute/unmute player volume."""
        self._state = self._player.mute(mute)

    def turn_off(self):
        """Turn off media player."""
        self._media_title = None
        self._state = self._player.turn_off()
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn off media player."""
        self._state = self._player.turn_on()
        self.schedule_update_ha_state()

    def media_play(self):
        """Play media player."""
        self._state = self._player.play()
        self.schedule_update_ha_state()

    def media_pause(self):
        """Pause media player."""
        self._state = self._player.pause()
        self.schedule_update_ha_state()

    @property
    def media_title(self):
        """Return the current media source."""
        self.__update_title()
        if self._media_title:
            return self._media_title
        return self._state.get('playback_url', 'Not playing')

    def __update_title(self):
        if self._state['player_state'] == 'bluray_playback':
            self._media_title = 'Blu-Ray'
        elif 'playback_url' in self._state:
            sources = self._sources
            sval = sources.values()
            skey = sources.keys()
            pburl = self._state['playback_url']
            if pburl in sval:
                self._media_title = list(skey)[list(sval).index(pburl)]
            else:
                self._media_title = pburl

    def select_source(self, source):
        """Select input source."""
        self._media_title = source
        self._state = self._player.launch_media_url(self._sources.get(source))
        self.schedule_update_ha_state()

    def media_previous_track(self):
        """Send previous track command."""
        self._state = self._player.previous_track()
        self.schedule_update_ha_state()

    def media_next_track(self):
        """Send next track command."""
        self._state = self._player.next_track()
        self.schedule_update_ha_state()
