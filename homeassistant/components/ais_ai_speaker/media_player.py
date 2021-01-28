"""Support to interact with a AIS Player."""
import logging
from typing import Optional

from homeassistant.components.media_player import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .media_browser import async_browse_media

_LOGGER = logging.getLogger(__name__)

SUPPORT_AIS = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_BROWSE_MEDIA
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the AIS Player."""
    _LOGGER.debug("AI-Speaker player, async_setup_entry")
    ais_gate_instance = hass.data[DOMAIN][config_entry.entry_id]
    ais_player = AisPlayerDevice(ais_gate_instance)
    async_add_entities([ais_player], True)


class AisPlayerDevice(MediaPlayerEntity):
    """Representation of a AIS Player ."""

    def turn_off(self):
        """Turn off the player."""

    def clear_playlist(self):
        """Clear the media player playlist."""

    def set_repeat(self, repeat):
        """Set the repeat for the AIS player."""

    def turn_on(self):
        """Turn on the player."""

    def __init__(self, ais_gate_instance):
        """Initialize the Ais Player device."""
        self._ais_gate = ais_gate_instance
        self._ais_id = None
        self._ais_ws_url = None
        self._ais_product = None
        self._ais_manufacturer = None
        self._ais_model = None
        self._ais_os_version = None
        self._status = None
        self._playing = False
        self._stream_image = None
        self._media_title = None
        self._media_source = None
        self._album_name = None
        self._sound_mode = "NORMAL"
        self._media_status_received_time = None
        self._media_position = 0
        self._duration = 0
        self._media_id = None
        self._volume_level = 0.5
        self._shuffle = False

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._ais_id)},
            "name": "AI-Speaker player",
            "manufacturer": self._ais_manufacturer,
            "model": self._ais_model,
            "sw_version": self._ais_os_version,
            "via_device": None,
        }

    async def async_set_volume_level(self, volume):
        """Set the volume level."""
        self._volume_level = volume
        vol = int(volume * 100)
        await self._ais_gate.command("setVolume", vol)

    def select_sound_mode(self, sound_mode):
        """Set the sound mode."""
        self._sound_mode = sound_mode

    async def async_fetch_status(self):
        """Fetch status from AIS."""
        ais_info = await self._ais_gate.get_gate_info()
        if ais_info is None:
            _LOGGER.warning("Problem to fetch status from AI Speaker %s", ais_info)
            return
        self._ais_id = ais_info["ais_id"]
        self._ais_ws_url = ais_info["ais_url"]
        self._ais_product = ais_info.get("Product", "Player")
        self._ais_manufacturer = ais_info.get("Manufacturer", "AIS")
        self._ais_model = ais_info.get("Model", "Speaker")

        audio_status = await self._ais_gate.get_audio_status()
        if audio_status is not None:
            self._volume_level = audio_status.get("currentVolume", 100) / 100
            self._status = audio_status.get("currentStatus", None)
            self._playing = audio_status.get("playing", False)
            self._media_position = audio_status.get("currentPosition", None)
            self._duration = audio_status.get("duration", None)
            self._stream_image = audio_status.get("media_stream_image", None)
            self._media_title = audio_status.get("currentMedia", "AI-Speaker")
            self._media_source = audio_status.get("media_source", self._media_source)
            self._album_name = audio_status.get("media_album_name", "AI-Speaker")
        else:
            _LOGGER.error("Fetch status from AIS")

    @property
    def volume_level(self):
        """Return the volume level of the Player."""
        return self._volume_level

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return float(self._duration) / 1000

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffle

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return [
            "NORMAL",
            "BOOST",
            "TREBLE",
            "POP",
            "ROCK",
            "CLASSIC",
            "JAZZ",
            "DANCE",
            "R&P",
        ]

    @property
    def available(self):
        """Return true if AIS Player is available and connected."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return "AI-Speaker player"

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        if self._stream_image == "null":
            return None

        return self._stream_image

    @property
    def state(self):
        """Return the media state."""
        if self._playing is False:
            return STATE_PAUSED
        if self._status == 1:
            return STATE_IDLE
        if self._status == 2:
            return STATE_PAUSED
        if self._status == 3:
            return STATE_PLAYING
        if self._status == 4:
            return STATE_PAUSED

        return STATE_OFF

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_album_name(self):
        """Return album of current playing media."""
        # return self._album_name
        return ""

    @property
    def app_name(self):
        """Name of the current running app."""
        app = None
        if self._media_source is not None:
            app = self._media_source
            if self._album_name is not None:
                app = str(app) + " " + str(self._album_name)
        return app

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_AIS

    @property
    def media_content_id(self):
        """Return the media content id."""
        return self._media_id

    @property
    def media_stream_image(self):
        """Return the media content id."""
        return self._stream_image

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        position = float(self._media_position) // 1000
        return int(position)

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of the player."""
        return {
            "ais_id": self._ais_id,
            "ais_ws_url": self._ais_ws_url,
            "ais_exo_version": "2.2",
        }

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._ais_id

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_status_received_time

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        await self._ais_gate.command("setPlayerShuffle", self._shuffle)

    async def async_media_seek(self, position):
        """Seek the media to a specific location."""
        if position == 0:
            val = -5000
        elif position == 1:
            val = 5000
        else:
            val = position * 1000
            self._media_status_received_time = dt_util.utcnow()
            self._media_position = position * 1000
        await self._ais_gate.command("seekTo", val)

    async def async_volume_up(self):
        """Service to send the exo the command for volume up."""
        self._volume_level = min(self._volume_level + 0.0667, 1)
        await self._ais_gate.command("upVolume", True)

    async def async_volume_down(self):
        """Service to send the exo the command for volume down."""
        self._volume_level = max(self._volume_level - 0.0667, 0)
        await self._ais_gate.command("downVolume", True)

    async def async_mute_volume(self, mute):
        """Service to send the exo the command for mute."""
        await self._ais_gate.command("setVolume", 0)

    async def async_update(self):
        """Get the latest data and update the state."""
        await self.async_fetch_status()

    async def async_media_play(self):
        """Service to send the AIS Player the command for play/pause."""
        await self._ais_gate.command("pauseAudio", False)
        self._playing = True
        self._status = 3

    async def async_media_pause(self):
        """Service to send the AIS Player the command for play/pause."""
        await self._ais_gate.command("pauseAudio", True)
        self._playing = False

    async def async_media_stop(self):
        """Service to send the AIS Player the command for stop."""
        await self._ais_gate.command("pauseAudio", True)
        self._playing = False

    async def async_media_next_track(self):
        """Service to send the AIS Player the command for next track."""
        await self._ais_gate.command("playNext", False)

    async def async_media_previous_track(self):
        """Service to send the AIS Player the command for previous track."""
        await self._ais_gate.command("playPrev", False)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a media."""
        self._media_id = await self._ais_gate.get_media_content_id_form_ais(media_id)
        self._media_position = 0
        self._media_status_received_time = dt_util.utcnow()
        await self._ais_gate.command("playAudio", self._media_id)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the media browsing helper."""
        result = await async_browse_media(
            media_content_type,
            media_content_id,
            self._ais_gate,
        )
        await self._ais_gate.cache_browse_media(result.as_dict())
        return result
