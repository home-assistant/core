"""Dune HD implementation of the media player."""

from __future__ import annotations

from typing import Any, Final

from pdunehd import DuneHDPlayer

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DEFAULT_NAME, DOMAIN

CONF_SOURCES: Final = "sources"

DUNEHD_PLAYER_SUPPORT: Final[MediaPlayerEntityFeature] = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Dune HD entities from a config_entry."""
    unique_id = entry.entry_id

    player: DuneHDPlayer = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([DuneHDPlayerEntity(player, DEFAULT_NAME, unique_id)], True)


class DuneHDPlayerEntity(MediaPlayerEntity):
    """Implementation of the Dune HD player."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, player: DuneHDPlayer, name: str, unique_id: str) -> None:
        """Initialize entity to control Dune HD."""
        self._player = player
        self._media_title: str | None = None
        self._state: dict[str, Any] = {}
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            name=name,
        )

    def update(self) -> None:
        """Update internal status of the entity."""
        self._state = self._player.update_state()
        self.__update_title()

    @property
    def state(self) -> MediaPlayerState:
        """Return player state."""
        state = MediaPlayerState.OFF
        if "playback_position" in self._state:
            state = MediaPlayerState.PLAYING
        if self._state.get("player_state") in ("playing", "buffering", "photo_viewer"):
            state = MediaPlayerState.PLAYING
        if int(self._state.get("playback_speed", 1234)) == 0:
            state = MediaPlayerState.PAUSED
        if self._state.get("player_state") == "navigator":
            state = MediaPlayerState.ON
        return state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return len(self._state) > 0

    @property
    def volume_level(self) -> float:
        """Return the volume level of the media player (0..1)."""
        return int(self._state.get("playback_volume", 0)) / 100

    @property
    def is_volume_muted(self) -> bool:
        """Return a boolean if volume is currently muted."""
        return int(self._state.get("playback_mute", 0)) == 1

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return DUNEHD_PLAYER_SUPPORT

    def volume_up(self) -> None:
        """Volume up media player."""
        self._state = self._player.volume_up()

    def volume_down(self) -> None:
        """Volume down media player."""
        self._state = self._player.volume_down()

    def mute_volume(self, mute: bool) -> None:
        """Mute/unmute player volume."""
        self._state = self._player.mute(mute)

    def turn_off(self) -> None:
        """Turn off media player."""
        self._media_title = None
        self._state = self._player.turn_off()

    def turn_on(self) -> None:
        """Turn on media player."""
        self._state = self._player.turn_on()

    def media_play(self) -> None:
        """Play media player."""
        self._state = self._player.play()

    def media_pause(self) -> None:
        """Pause media player."""
        self._state = self._player.pause()

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from a URL or file."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        # If media ID is a relative URL, we serve it from HA.
        media_id = async_process_play_media_url(self.hass, media_id)

        self._state = await self.hass.async_add_executor_job(
            self._player.launch_media_url, media_id
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)

    @property
    def media_title(self) -> str | None:
        """Return the current media source."""
        self.__update_title()
        if self._media_title:
            return self._media_title
        return None

    def __update_title(self) -> None:
        if self._state.get("player_state") == "bluray_playback":
            self._media_title = "Blu-Ray"
        elif self._state.get("player_state") == "photo_viewer":
            self._media_title = "Photo Viewer"
        elif self._state.get("playback_url"):
            self._media_title = self._state["playback_url"].split("/")[-1]
        else:
            self._media_title = None

    def media_previous_track(self) -> None:
        """Send previous track command."""
        self._state = self._player.previous_track()

    def media_next_track(self) -> None:
        """Send next track command."""
        self._state = self._player.next_track()
