"""Support for Apple TV media player."""
import logging

from pyatv.const import DeviceState, MediaType

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_VIDEO,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import callback
import homeassistant.util.dt as dt_util

from . import AppleTVEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SUPPORT_APPLE_TV = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Apple TV media player based on a config entry."""
    name = config_entry.data[CONF_NAME]
    manager = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([AppleTvMediaPlayer(name, config_entry.unique_id, manager)])


class AppleTvMediaPlayer(AppleTVEntity, MediaPlayerEntity):
    """Representation of an Apple TV media player."""

    def __init__(self, name, identifier, manager, **kwargs):
        """Initialize the Apple TV media player."""
        super().__init__(name, identifier, manager, **kwargs)
        self._playing = None

    @callback
    def async_device_connected(self, atv):
        """Handle when connection is made to device."""
        self.atv.push_updater.listener = self
        self.atv.push_updater.start()

    @callback
    def async_device_disconnected(self):
        """Handle when connection was lost to device."""
        self.atv.push_updater.stop()
        self.atv.push_updater.listener = None

    @property
    def state(self):
        """Return the state of the device."""
        if self.manager.is_connecting:
            return None
        if self.atv is None:
            return STATE_OFF
        if self._playing:
            state = self._playing.device_state
            if state in (DeviceState.Idle, DeviceState.Loading):
                return STATE_IDLE
            if state == DeviceState.Playing:
                return STATE_PLAYING
            if state in (DeviceState.Paused, DeviceState.Seeking, DeviceState.Stopped):
                return STATE_PAUSED
            return STATE_STANDBY  # Bad or unknown state?
        return None

    @callback
    def playstatus_update(self, _, playing):
        """Print what is currently playing when it changes."""
        self._playing = playing
        self.async_write_ha_state()

    @callback
    def playstatus_error(self, _, exception):
        """Inform about an error and restart push updates."""
        _LOGGER.warning("A %s error occurred: %s", exception.__class__, exception)
        self._playing = None
        self.async_write_ha_state()

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._playing:
            return {
                MediaType.Video: MEDIA_TYPE_VIDEO,
                MediaType.Music: MEDIA_TYPE_MUSIC,
                MediaType.TV: MEDIA_TYPE_TVSHOW,
            }.get(self._playing.media_type)
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._playing:
            return self._playing.total_time
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._playing:
            return self._playing.position
        return None

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        if self.state in (STATE_PLAYING, STATE_PAUSED):
            return dt_util.utcnow()
        return None

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        await self.atv.stream.play_url(media_id)

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        state = self.state
        if self._playing and state not in [None, STATE_OFF, STATE_IDLE]:
            return self.atv.metadata.artwork_id
        return None

    async def async_get_media_image(self):
        """Fetch media image of current playing image."""
        state = self.state
        if self._playing and state not in [STATE_OFF, STATE_IDLE]:
            artwork = await self.atv.metadata.artwork()
            if artwork:
                return artwork.bytes, artwork.mimetype

        return None, None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._playing:
            return self._playing.title
        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_APPLE_TV

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.manager.connect()

    async def async_turn_off(self):
        """Turn the media player off."""
        self._playing = None
        await self.manager.disconnect()

    async def async_media_play_pause(self):
        """Pause media on media player."""
        if self._playing:
            state = self.state
            if state == STATE_PAUSED:
                await self.atv.remote_control.play()
            elif state == STATE_PLAYING:
                await self.atv.remote_control.pause()
        return None

    async def async_media_play(self):
        """Play media."""
        if self._playing:
            await self.atv.remote_control.play()

    async def async_media_stop(self):
        """Stop the media player."""
        if self._playing:
            await self.atv.remote_control.stop()

    async def async_media_pause(self):
        """Pause the media player."""
        if self._playing:
            await self.atv.remote_control.pause()

    async def async_media_next_track(self):
        """Send next track command."""
        if self._playing:
            await self.atv.remote_control.next()

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._playing:
            await self.atv.remote_control.previous()

    async def async_media_seek(self, position):
        """Send seek command."""
        if self._playing:
            await self.atv.remote_control.set_position(position)
