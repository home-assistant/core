"""Provide functionality to interact with the vlc telnet interface."""
from __future__ import annotations

from python_telnet_vlc import (
    AuthError,
    CommandError,
    ConnectionError as ConnErr,
    LuaError,
    ParseError,
)
from python_telnet_vlc.vlctelnet import VLCTelnet
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import DATA_AVAILABLE, DATA_VLC, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, LOGGER

MAX_VOLUME = 500

SUPPORT_VLC = (
    SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SEEK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the vlc platform."""
    LOGGER.warning(
        "Loading VLC media player Telnet integration via platform setup is deprecated; "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the vlc platform."""
    name = entry.data[CONF_NAME]
    vlc = hass.data[DOMAIN][entry.entry_id][DATA_VLC]
    available = hass.data[DOMAIN][entry.entry_id][DATA_AVAILABLE]

    async_add_entities([VlcDevice(entry, vlc, name, available)], True)


class VlcDevice(MediaPlayerEntity):
    """Representation of a vlc player."""

    def __init__(
        self, config_entry: ConfigEntry, vlc: VLCTelnet, name: str, available: bool
    ) -> None:
        """Initialize the vlc device."""
        self._config_entry = config_entry
        self._name = name
        self._volume = None
        self._muted = None
        self._state = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_duration = None
        self._vlc = vlc
        self._available = available
        self._volume_bkp = 0
        self._media_artist = None
        self._media_title = None

    def update(self):
        """Get the latest details from the device."""
        if not self._available:
            try:
                self._vlc.connect()
            except (ConnErr, EOFError) as err:
                LOGGER.debug("Connection error: %s", err)
                return

            try:
                self._vlc.login()
            except AuthError:
                LOGGER.debug("Failed to login to VLC")
                self.hass.add_job(
                    self.hass.config_entries.async_reload, self._config_entry.entry_id
                )
                return

            self._state = STATE_IDLE
            self._available = True
            LOGGER.info("Connected to vlc host: %s", self._vlc.host)

        try:
            status = self._vlc.status()
            LOGGER.debug("Status: %s", status)

            if status:
                if "volume" in status:
                    self._volume = status["volume"] / MAX_VOLUME
                else:
                    self._volume = None
                if "state" in status:
                    state = status["state"]
                    if state == "playing":
                        self._state = STATE_PLAYING
                    elif state == "paused":
                        self._state = STATE_PAUSED
                    else:
                        self._state = STATE_IDLE
                else:
                    self._state = STATE_IDLE

            if self._state != STATE_IDLE:
                self._media_duration = self._vlc.get_length()
                vlc_position = self._vlc.get_time()

                # Check if current position is stale.
                if vlc_position != self._media_position:
                    self._media_position_updated_at = dt_util.utcnow()
                    self._media_position = vlc_position

            info = self._vlc.info()
            LOGGER.debug("Info: %s", info)

            if info:
                self._media_artist = info.get(0, {}).get("artist")
                self._media_title = info.get(0, {}).get("title")

                if not self._media_title:
                    # Fall back to filename.
                    data_info = info.get("data")
                    if data_info:
                        self._media_title = data_info["filename"]

        except (CommandError, LuaError, ParseError) as err:
            LOGGER.error("Command error: %s", err)
        except (ConnErr, EOFError) as err:
            if self._available:
                LOGGER.error("Connection error: %s", err)
                self._available = False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_VLC

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_artist

    def media_seek(self, position):
        """Seek the media to a specific location."""
        self._vlc.seek(int(position))

    def mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            self._volume_bkp = self._volume
            self.set_volume_level(0)
        else:
            self.set_volume_level(self._volume_bkp)

        self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._vlc.set_volume(volume * MAX_VOLUME)
        self._volume = volume

        if self._muted and self._volume > 0:
            # This can happen if we were muted and then see a volume_up.
            self._muted = False

    def media_play(self):
        """Send play command."""
        self._vlc.play()
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        current_state = self._vlc.status().get("state")
        if current_state != "paused":
            # Make sure we're not already paused since VLCTelnet.pause() toggles
            # pause.
            self._vlc.pause()
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send stop command."""
        self._vlc.stop()
        self._state = STATE_IDLE

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if media_type != MEDIA_TYPE_MUSIC:
            LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_MUSIC,
            )
            return
        self._vlc.add(media_id)
        self._state = STATE_PLAYING

    def media_previous_track(self):
        """Send previous track command."""
        self._vlc.prev()

    def media_next_track(self):
        """Send next track command."""
        self._vlc.next()

    def clear_playlist(self):
        """Clear players playlist."""
        self._vlc.clear()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._vlc.random(shuffle)
