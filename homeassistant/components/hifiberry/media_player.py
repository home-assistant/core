"""Hifiberry Platform."""
import logging
from datetime import timedelta

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from pyhifiberry.audiocontrol2 import Audiocontrol2Exception, LOGGER
from .const import DATA_HIFIBERRY, DATA_INIT, DOMAIN

SUPPORT_HIFIBERRY = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_STOP
    | SUPPORT_PLAY
    | SUPPORT_VOLUME_STEP
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=2)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the hifiberry media player platform."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    audiocontrol2 = data[DATA_HIFIBERRY]
    meta, volume = data[DATA_INIT]
    uid = config_entry.entry_id
    name = f"hifiberry {config_entry.data['host']}"

    entity = HifiberryMediaPlayer(audiocontrol2, meta, volume, uid, name)
    _LOGGER.debug("Vetadata: %s, Volume: %s", meta, volume)
    async_add_entities([entity])


class HifiberryMediaPlayer(MediaPlayerEntity):
    """Hifiberry Media Player Object."""

    def __init__(self, audiocontrol2, metadata, volume, uid, name):
        """Initialize the media player."""
        self._audiocontrol2 = audiocontrol2
        self._uid = uid
        self._name = name
        self._muted = volume == 0
        self._volume = self._muted_volume = volume
        self._metadata = metadata
        self._available = None

    @property
    def available(self) -> bool:
        """Return true if device is responding."""
        return self._available

    @property
    def unique_id(self):
        """Return the unique id for the entity."""
        return self._uid

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Hifiberry",
        }

    async def async_update(self):
        """Update state."""
        try:
            self._metadata = await self._audiocontrol2.metadata()
            self._volume = await self._audiocontrol2.volume()
            LOGGER.debug("Metadata: %s", self._metadata)
            self._available = True
        except Audiocontrol2Exception:
            self._available = False

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        status = self._metadata.get("playerState", None)
        if status == "paused":
            return STATE_PAUSED
        if status == "playing":
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._metadata.get("positionupdate", None)

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._metadata.get("title", None)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._metadata.get("artist", None)

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        return self._metadata.get("albumTitle", None)

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return self._metadata.get("albumArtist", None)

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self._metadata.get("tracknumber", None)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        art_url = self._metadata.get("artUrl", None)
        external_art_url = self._metadata.get("externalArtUrl", None)
        if art_url is not None:
            if art_url.startswith("static/"):
                return external_art_url
            if art_url.startswith("artwork/"):
                return f"{self._audiocontrol2.base_url}/{art_url}"
            return art_url
        return external_art_url

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return int(self._volume) / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def source(self):
        """Name of the current input source."""
        return self._metadata.get("playerName")

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_HIFIBERRY

    async def async_media_next_track(self):
        """Send media_next command to media player."""
        await self._audiocontrol2.player("next")

    async def async_media_previous_track(self):
        """Send media_previous command to media player."""
        await self._audiocontrol2.player("previous")

    async def async_media_play(self):
        """Send media_play command to media player."""
        await self._audiocontrol2.player("play")

    async def async_media_pause(self):
        """Send media_pause command to media player."""
        await self._audiocontrol2.player("pause")

    async def async_volume_up(self):
        """Service to send the hifiberry the command for volume up."""
        await self._audiocontrol2.volume("+5")
        self._volume += 5

    async def async_volume_down(self):
        """Service to send the hifiberry the command for volume down."""
        await self._audiocontrol2.volume("-5")
        self._volume -= 5

    async def async_set_volume_level(self, volume):
        """Send volume_set command to media player."""
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        await self._audiocontrol2.volume(int(volume * 100))
        self._volume = volume * 100

    async def async_mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        if mute:
            self._muted_volume = self.volume_level
            await self._audiocontrol2.volume(0)
        await self._audiocontrol2.volume(int(self._muted_volume * 100))
        self._muted = mute
