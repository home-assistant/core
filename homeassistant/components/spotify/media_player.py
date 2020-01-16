"""Support for interacting with Spotify Connect."""
from asyncio import run_coroutine_threadsafe
from datetime import timedelta
import logging
import random
from typing import Any, Callable, Dict, List, Optional

import spotipy
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import CONF_ALIASES, DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_PLAY_PLAYLIST = "play_playlist"
ATTR_RANDOM_SONG = "random_song"

PLAY_PLAYLIST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
        vol.Optional(ATTR_RANDOM_SONG, default=False): cv.boolean,
    }
)

ICON = "mdi:spotify"

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_SPOTIFY = (
    SUPPORT_VOLUME_SET
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_SHUFFLE_SET
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Spotify platform."""
    # def play_playlist_service(service):
    #     media_content_id = service.data[ATTR_MEDIA_CONTENT_ID]
    #     random_song = service.data.get(ATTR_RANDOM_SONG)
    #     player.play_playlist(media_content_id, random_song)

    # hass.services.register(
    #     DOMAIN,
    #     SERVICE_PLAY_PLAYLIST,
    #     play_playlist_service,
    #     schema=PLAY_PLAYLIST_SCHEMA,
    # )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Spotify based on a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    player = SpotifyMediaPlayer(
        session,
        entry.data[CONF_ID],
        entry.data[CONF_NAME],
        hass.data[DOMAIN].get(CONF_ALIASES, {}),
    )

    async_add_entities([player], True)


class SpotifyMediaPlayer(MediaPlayerDevice):
    """Representation of a Spotify controller."""

    def __init__(self, session, user_id, name, aliases):
        """Initialize."""
        self._name = f"Spotify {name}"
        self._id = user_id
        self._session = session
        self._album = None
        self._title = None
        self._artist = None
        self._uri = None
        self._image_url = None
        self._state = None
        self._current_device = None
        self._devices = {}
        self._volume = None
        self._shuffle = False
        self._player = None
        self._user = None
        self._aliases = aliases

    def refresh_spotify_instance(self) -> None:
        """Refresh a new Spotify instance."""
        if not self._session.valid_token or self._player is None:
            run_coroutine_threadsafe(
                self._session.async_ensure_token_valid(), self.hass.loop
            ).result()
            self._player = spotipy.Spotify(auth=self._session.token["access_token"])
            self._user = self._player.me()

    def update(self) -> None:
        """Update state and attributes."""
        self.refresh_spotify_instance()

        # Available devices
        player_devices = self._player.devices()
        if player_devices is not None:
            devices = player_devices.get("devices")
            if devices is not None:
                old_devices = self._devices
                self._devices = {
                    self._aliases.get(device.get("id"), device.get("name")): device.get(
                        "id"
                    )
                    for device in devices
                }
                device_diff = {
                    name: id
                    for name, id in self._devices.items()
                    if old_devices.get(name, None) is None
                }
                if device_diff:
                    _LOGGER.info("New Devices: %s", str(device_diff))

        # Current playback state
        current = self._player.current_playback()
        if current is None:
            self._state = STATE_IDLE
            return

        # Track metadata
        item = current.get("item")
        if item:
            self._album = item.get("album").get("name")
            self._title = item.get("name")
            self._artist = ", ".join(
                [artist.get("name") for artist in item.get("artists")]
            )
            self._uri = item.get("uri")
            images = item.get("album").get("images")
            self._image_url = images[0].get("url") if images else None

        # Playing state
        self._state = STATE_PAUSED
        if current.get("is_playing"):
            self._state = STATE_PLAYING
        self._shuffle = current.get("shuffle_state")
        device = current.get("device")
        if device is None:
            self._state = STATE_IDLE
        else:
            if device.get("volume_percent"):
                self._volume = device.get("volume_percent") / 100
            if device.get("name"):
                self._current_device = device.get("name")

    def set_volume_level(self, volume: int) -> None:
        """Set the volume level."""
        self._player.volume(int(volume * 100))

    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        self._player.shuffle(shuffle)

    def media_next_track(self) -> None:
        """Skip to next track."""
        self._player.next_track()

    def media_previous_track(self) -> None:
        """Skip to previous track."""
        self._player.previous_track()

    def media_play(self) -> None:
        """Start or resume playback."""
        self._player.start_playback()

    def media_pause(self) -> None:
        """Pause playback."""
        self._player.pause_playback()

    def select_source(self, source: str) -> None:
        """Select playback device."""
        if self._devices:
            self._player.transfer_playback(
                self._devices[source], self._state == STATE_PLAYING
            )

    def play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Play media."""
        kwargs = {}
        if media_type == MEDIA_TYPE_MUSIC:
            kwargs["uris"] = [media_id]
        elif media_type == MEDIA_TYPE_PLAYLIST:
            kwargs["context_uri"] = media_id
        else:
            _LOGGER.error("media type %s is not supported", media_type)
            return
        if not media_id.startswith("spotify:"):
            _LOGGER.error("media id must be spotify uri")
            return
        self._player.start_playback(**kwargs)

    def play_playlist(self, media_id, random_song) -> None:
        """Play random music in a playlist."""
        if not media_id.startswith("spotify:"):
            _LOGGER.error("media id must be spotify playlist uri")
            return
        kwargs = {"context_uri": media_id}
        if random_song:
            results = self._player.user_playlist_tracks("me", media_id)
            position = random.randint(0, results["total"] - 1)
            kwargs["offset"] = {"position": position}
        self._player.start_playback(**kwargs)

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return ICON

    @property
    def state(self) -> Optional[str]:
        """Return the playback state."""
        return self._state

    @property
    def volume_level(self) -> int:
        """Return the device volume."""
        return self._volume

    @property
    def shuffle(self) -> bool:
        """Shuffling state."""
        return self._shuffle

    @property
    def source_list(self) -> List[str]:
        """Return a list of source devices."""
        if self._devices:
            return list(self._devices.keys())

    @property
    def source(self) -> str:
        """Return the current playback device."""
        return self._current_device

    @property
    def media_content_id(self) -> str:
        """Return the media URL."""
        return self._uri

    @property
    def media_image_url(self) -> str:
        """Return the media image URL."""
        return self._image_url

    @property
    def media_artist(self) -> str:
        """Return the media artist."""
        return self._artist

    @property
    def media_album_name(self) -> str:
        """Return the media album."""
        return self._album

    @property
    def media_title(self) -> str:
        """Return the media title."""
        return self._title

    @property
    def supported_features(self) -> int:
        """Return the media player features that are supported."""
        if self._user is not None and self._user["product"] == "premium":
            return SUPPORT_SPOTIFY
        return None

    @property
    def media_content_type(self) -> str:
        """Return the media type."""
        return MEDIA_TYPE_MUSIC

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._id

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        model = ""
        if self._user is not None:
            model = self._user["product"]

        return {
            "identifiers": {(DOMAIN, self._id)},
            "manufacturer": "Spotify AB",
            "model": f"Spotify {model}".rstrip(),
            "name": self._name,
        }
