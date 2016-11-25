"""
DuneHD implementation of the media player.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/dunehd/
"""
from homeassistant.components.media_player import (
	MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_NEXT_TRACK,
	SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
	SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
	SUPPORT_SELECT_SOURCE, SUPPORT_CLEAR_PLAYLIST, PLATFORM_SCHEMA, MediaPlayerDevice)
from homeassistant.const import (CONF_HOST, CONF_NAME, STATE_OFF, STATE_PAUSED, STATE_PLAYING)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['pdunehd==1.0']

DEFAULT_NAME = "DuneHD"

CONF_SOURCES = "sources"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_HOST): cv.string,
	vol.Optional(CONF_SOURCES): cv.ordered_dict(cv.string, cv.string),
	vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

DUNEHD_PLAYER_SUPPORT = \
	SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
	"""Setup the media player demo platform."""
	sources = config.get(CONF_SOURCES, {})

	from pdunehd import DuneHDPlayer
	add_devices([DuneHDPlayerEntity(DuneHDPlayer(config[CONF_HOST]), config[CONF_NAME], sources)])

class DuneHDPlayerEntity(MediaPlayerDevice):
	def __init__(self, player, name, sources):
		self._player = player
		self._name = name
		self._sources = sources
		self.update()

	def update(self):
		self._state = self._player.updateState()
		return True

	@property
	def state(self):
		if 'playback_state' in self._state:
			if self._state['playback_state'] == 'playing':
				return STATE_PLAYING
			else:
				return STATE_PAUSED
		return STATE_OFF

	@property
	def name(self):
		"""Return the name of the device."""
		return self._name

	@property
	def volume_level(self):
		"""Volume level of the media player (0..1)."""
		return int(self._state.get('playback_volume', 0)) / 100

	@property
	def is_volume_muted(self):
		"""Boolean if volume is currently muted."""
		return int(self._state.get('playback_mute', 0)) == 1

	@property
	def source_list(self):
		"""List of available input sources."""
		return list(self._sources.keys())

	@property
	def supported_media_commands(self):
		"""Flag of media commands that are supported."""
		return DUNEHD_PLAYER_SUPPORT

	def volume_up(self):
		"""Volume up media player."""
		self._player.volumeUp()

	def volume_down(self):
		"""Volume down media player."""
		self._player.volumeDown()

	def mute_volume(self, mute):
		self._player.mute(mute)

	def turn_off(self):
		"""Turn off media player."""
		self._player.stop()

	def turn_on(self):
		"""Turn off media player."""
		self._player.stop()

	def media_play(self):
		"""Play media media player."""
		self._player.play()

	def media_pause(self):
		"""Pause media player."""
		self._player.pause()

	@property
	def media_title(self):
		"""Current media source."""
		return self._state.get('playback_url', 'Not playing')

	def select_source(self, source):
		"""Select input source."""
		self._player.launchMediaUrl(self._sources.get(source))