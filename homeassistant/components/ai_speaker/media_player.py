"""Support to interact with a AIS Player."""
import logging
from typing import Optional

from aisapi.ws import AisWebService
import requests

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
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
from homeassistant.helpers import aiohttp_client
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .media_browser import async_browse_media

_LOGGER = logging.getLogger(__name__)

SUPPORT_AIS = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_BROWSE_MEDIA
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the AIS Player."""

    ais_player = AisPlayerDevice(config_entry.data, hass)
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

    def __init__(self, config_entry_data, hass):
        """Initialize the Ais Player device."""
        self._ais_info = config_entry_data.get("ais_info")
        self._ais_id = self._ais_info.get("ais_id")
        self._ais_ws_url = self._ais_info.get("ais_url")
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
        self._web_session = aiohttp_client.async_get_clientsession(hass)
        self._ais_gate = AisWebService(hass.loop, self._web_session, self._ais_ws_url)

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._ais_id)},
            "name": "AI-Speaker",
            "manufacturer": self._ais_info["Manufacturer"],
            "model": self._ais_info["Model"],
            "sw_version": self._ais_info["OsVersion"],
            "via_device": None,
        }

    def set_volume_level(self, volume):
        """Set the volume level."""
        self._volume_level = volume
        vol = int(volume * 100)
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "setVolume", "val": vol, "ais_url": self._ais_ws_url},
        )

    def select_sound_mode(self, sound_mode):
        """Set the sound mode."""
        self._sound_mode = sound_mode

    async def async_fetch_status(self):
        """Fetch status from AIS."""
        audio_status = await self._ais_gate.get_audio_status()
        if audio_status is not None:
            self._volume_level = audio_status.get("currentVolume", 100) / 100
            self._status = audio_status.get("currentStatus", 0)
            self._playing = audio_status.get("playing", False)
            self._media_position = audio_status.get("currentPosition", 0)
            self._duration = audio_status.get("duration", 0)
            self._stream_image = audio_status.get("media_stream_image", None)
            self._media_title = audio_status.get("currentMedia", "AI-Speaker")
            self._media_source = audio_status.get("media_source", self._media_source)
            self._album_name = audio_status.get("media_album_name", "AI-Speaker")
        else:
            _LOGGER.error("Fetch status from AIS")

    def select_source(self, source):
        """Choose a different available playlist and play it."""

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

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {
                "key": "setPlayerShuffle",
                "val": self._shuffle,
                "ais_url": self._ais_ws_url,
            },
        )

    def media_seek(self, position):
        """Seek the media to a specific location."""
        if position == 0:
            val = -5000
        elif position == 1:
            val = 5000
        else:
            val = position * 1000
            self._media_status_received_time = dt_util.utcnow()
            self._media_position = position * 1000
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "seekTo", "val": val, "ais_url": self._ais_ws_url},
        )

    def volume_up(self):
        """Service to send the exo the command for volume up."""
        self._volume_level = min(self._volume_level + 0.0667, 1)
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "upVolume", "val": True, "ais_url": self._ais_ws_url},
        )

    def volume_down(self):
        """Service to send the exo the command for volume down."""
        self._volume_level = max(self._volume_level - 0.0667, 0)
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "downVolume", "val": True, "ais_url": self._ais_ws_url},
        )

    def mute_volume(self, mute):
        """Service to send the exo the command for mute."""
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "setVolume", "val": 0, "ais_url": self._ais_ws_url},
        )

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

    async def async_update(self):
        """Get the latest data and update the state."""
        await self.async_fetch_status()

    @property
    def name(self):
        """Return the name of the device."""
        return "AI-Speaker " + self._ais_info["Product"] + " player"

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
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
        return self._album_name

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
        return self._ais_info

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._ais_id

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_status_received_time

    def media_play(self):
        """Service to send the AIS Player the command for play/pause."""
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "pauseAudio", "val": False, "ais_url": self._ais_ws_url},
        )
        self._playing = True
        self._status = 3

    def media_pause(self):
        """Service to send the AIS Player the command for play/pause."""
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "pauseAudio", "val": True, "ais_url": self._ais_ws_url},
        )
        self._playing = False

    def media_stop(self):
        """Service to send the AIS Player the command for stop."""
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "pauseAudio", "val": True, "ais_url": self._ais_ws_url},
        )
        self._playing = False

    def media_next_track(self):
        """Service to send the AIS Player the command for next track."""
        self.hass.services.call(
            "ais_cloud", "play_next", {"media_source": self._media_source}
        )

    def media_previous_track(self):
        """Service to send the AIS Player the command for previous track."""
        self.hass.services.call(
            "ais_cloud", "play_prev", {"media_source": self._media_source}
        )

    def play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a media."""
        if media_id.startswith("ais_tunein"):
            url_to_call = media_id.split("/", 3)[3]
            try:
                response_text = requests.get(url_to_call, timeout=2).text
                response_text = response_text.split("\n")[0]
                if response_text.endswith(".pls"):
                    response_text = requests.get(response_text, timeout=2).text
                    media_id = response_text.split("\n")[1].replace("File1=", "")
                elif response_text.startswith("mms:"):
                    response_text = requests.get(
                        response_text.replace("mms:", "http:"), timeout=2
                    ).text
                    media_id = response_text.split("\n")[1].replace("Ref1=", "")
                else:
                    media_id = response_text
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.e("AIS play_media error: %s", error)

        self._media_id = media_id
        self._media_position = 0
        self._media_status_received_time = dt_util.utcnow()
        self.hass.services.call(
            DOMAIN,
            "publish_command",
            {"key": "playAudio", "val": media_id, "ais_url": self._ais_ws_url},
        )

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the media browsing helper."""
        result = await async_browse_media(
            media_content_type,
            media_content_id,
            self._ais_gate,
        )
        return result
