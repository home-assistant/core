"""
Denon HEOS Media Player.
"""

import logging

import voluptuous as vol

from aioheos import AioHeosController

from homeassistant.components.media_player import (PLATFORM_SCHEMA,
                                                   MediaPlayerDevice)

from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP)

from homeassistant.const import (CONF_HOST, STATE_OFF, STATE_PAUSED,
                                 STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)


REQUIREMENTS = ['aioheos==0.3.1']

SUPPORT_HEOS = SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_PAUSE | \
        SUPPORT_PLAY_MEDIA | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
        SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST):
    cv.string,
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices,
                               discover_info=None):
    """Set up the HEOS platform."""
    host = config[CONF_HOST]

    controller = AioHeosController(hass.loop, host, verbose=True)
    await controller.connect(host=host)

    players = controller.get_players()
    players.sort()
    devices = [HeosMediaPlayer(hass, p) for p in players]
    async_add_devices(devices)


class HeosMediaPlayer(MediaPlayerDevice):
    """The HEOS player."""

    def __init__(self, hass, player):
        """Initialize."""
        self._hass = hass
        self._player = player
        self._state = None
        self._dispatcher_remove = None

        self._player.state_change_callback = self.update_state
        self._player.request_update()

    def update_state(self):
        async_dispatcher_send(self._hass, 'heos_update', [self])

    # async_dispatcher_send(hass, 'heos_update', devices)
    async def async_added_to_hass(self):
        """Device added to hass."""
        async def async_update_state(devices):
            """Update device state."""
            await self.async_update_ha_state(False)

        self._dispatcher_remove = async_dispatcher_connect(
            self._hass, 'heos_update', async_update_state)

    async def async_will_remove_from_hass(self):
        """Disconnect the device when removed."""
        if self._dispatcher_remove:
            self._dispatcher_remove()

    @property
    def name(self):
        """Return the name of the device."""
        return self._player.name

    @property
    def volume_level(self):
        """Volume level of the device (0..1)."""
        volume = self._player.volume
        return float(volume) / 100

    @property
    def state(self):
        """Get state."""
        self._state = self._player.play_state
        if self._state == 'stop':
            return STATE_OFF
        if self._state == 'pause':
            return STATE_PAUSED
        if self._state == 'play':
            return STATE_PLAYING
        return None

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_artist(self):
        """Artist of current playing media."""
        return self._player.media_artist

    @property
    def media_title(self):
        """Album name of current playing media."""
        return self._player.media_title

    @property
    def media_album_name(self):
        """Album name of current playing media."""
        return self._player.media_album

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return self._player.media_image_url

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._player.media_id

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._player.mute == 'on'

    async def async_mute_volume(self, mute):
        """Mute volume."""
        self._player.set_mute(mute)

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._player.duration / 1000.0

    @property
    def media_position_updated_at(self):
        """Get time when position updated."""
        return self._player.current_position_updated_at

    @property
    def media_position(self):
        """Get media position."""
        return self._player.current_position / 1000.0

    async def async_media_next_track(self):
        """Go TO next track."""
        self._player.play_next()

    async def async_media_previous_track(self):
        """Go TO previous track."""
        self._player.play_previous()

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_HEOS

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._player.set_volume(volume * 100)

    async def async_media_play(self):
        """Play media player."""
        self._player.play()

    async def async_media_stop(self):
        """Stop media player."""
        self._player.stop()

    async def async_media_pause(self):
        """Pause media player."""
        self._player.pause()
