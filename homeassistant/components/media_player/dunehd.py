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
from homeassistant.const import (CONF_HOST, STATE_OFF, STATE_PAUSED, STATE_PLAYING)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['pdunehd==1.0']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_HOST): cv.ensure_list,
})

DUNEHD_PLAYER_SUPPORT = \
	SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
	"""Setup the media player demo platform."""
	dev = []

	for host in config[CONF_HOST]:
		from pdunehd import DuneHDPlayer
		dev.append(DuneHDPlayerEntity(DuneHDPlayer(host)))

	add_devices(dev)

class DuneHDPlayerEntity(MediaPlayerDevice):
	def __init__(self, player):
		self._player = player

	def update(self):
		self._player.updateState()
		return True

	@property
	def state(self):
		state = self._player.updateState()
		if 'playback_state' in state:
			if state['playback_state'] == 'playing':
				return STATE_PLAYING
			else:
				return STATE_PAUSED
		return STATE_OFF

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
		return self._player.getLastState().get('playback_url', 'Not playing')