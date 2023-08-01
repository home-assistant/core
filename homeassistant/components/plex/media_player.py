"""Support to interface with the Plex API."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

import plexapi.exceptions
import requests.exceptions

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import is_internal_request

from .const import (
    COMMON_PLAYERS,
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN,
    NAME_FORMAT,
    PLEX_NEW_MP_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
    TRANSIENT_DEVICE_MODELS,
)
from .helpers import get_plex_data, get_plex_server
from .media_browser import browse_media
from .services import process_plex_payload

_PlexMediaPlayerT = TypeVar("_PlexMediaPlayerT", bound="PlexMediaPlayer")
_R = TypeVar("_R")
_P = ParamSpec("_P")

_LOGGER = logging.getLogger(__name__)


def needs_session(
    func: Callable[Concatenate[_PlexMediaPlayerT, _P], _R]
) -> Callable[Concatenate[_PlexMediaPlayerT, _P], _R | None]:
    """Ensure session is available for certain attributes."""

    @wraps(func)
    def get_session_attribute(
        self: _PlexMediaPlayerT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        if self.session is None:
            return None
        return func(self, *args, **kwargs)

    return get_session_attribute


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex media_player from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    registry = er.async_get(hass)

    @callback
    def async_new_media_players(new_entities):
        _async_add_entities(hass, registry, async_add_entities, server_id, new_entities)

    unsub = async_dispatcher_connect(
        hass, PLEX_NEW_MP_SIGNAL.format(server_id), async_new_media_players
    )
    get_plex_data(hass)[DISPATCHERS][server_id].append(unsub)
    _LOGGER.debug("New entity listener created")


@callback
def _async_add_entities(hass, registry, async_add_entities, server_id, new_entities):
    """Set up Plex media_player entities."""
    _LOGGER.debug("New entities: %s", new_entities)
    entities = []
    plexserver = get_plex_server(hass, server_id)
    for entity_params in new_entities:
        plex_mp = PlexMediaPlayer(plexserver, **entity_params)
        entities.append(plex_mp)

        # Migration to per-server unique_ids
        old_entity_id = registry.async_get_entity_id(
            MP_DOMAIN, DOMAIN, plex_mp.machine_identifier
        )
        if old_entity_id is not None:
            new_unique_id = f"{server_id}:{plex_mp.machine_identifier}"
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                plex_mp.machine_identifier,
                new_unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=new_unique_id)

    async_add_entities(entities, True)


class PlexMediaPlayer(MediaPlayerEntity):
    """Representation of a Plex device."""

    def __init__(self, plex_server, device, player_source, session=None):
        """Initialize the Plex device."""
        self.plex_server = plex_server
        self.device = device
        self.player_source = player_source

        self.device_make = None
        self.device_platform = None
        self.device_product = None
        self.device_title = None
        self.device_version = None
        self.machine_identifier = device.machineIdentifier
        self.session_device = None

        self._device_protocol_capabilities = None
        self._previous_volume_level = 1  # Used in fake muting
        self._volume_level = 1  # since we can't retrieve remotely
        self._volume_muted = False  # since we can't retrieve remotely

        self._attr_available = False
        self._attr_should_poll = False
        self._attr_state = MediaPlayerState.IDLE
        self._attr_unique_id = (
            f"{self.plex_server.machine_identifier}:{self.machine_identifier}"
        )

        # Initializes other attributes
        self.session = session

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        _LOGGER.debug("Added %s [%s]", self.entity_id, self.unique_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_MEDIA_PLAYER_SIGNAL.format(self.unique_id),
                self.async_refresh_media_player,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL.format(self.unique_id),
                self.async_update_from_websocket,
            )
        )

    @callback
    def async_refresh_media_player(self, device, session, source):
        """Set instance objects and trigger an entity state update."""
        _LOGGER.debug("Refreshing %s [%s / %s]", self.entity_id, device, session)
        self.device = device
        self.session = session
        if source:
            self.player_source = source
        self.async_schedule_update_ha_state(True)

        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.plex_server.machine_identifier),
        )

    @callback
    def async_update_from_websocket(self, state):
        """Update the entity based on new websocket data."""
        self.update_state(state)
        self.async_write_ha_state()

        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.plex_server.machine_identifier),
        )

    def update(self):
        """Refresh key device data."""
        if not self.session:
            self.force_idle()
            if not self.device:
                self._attr_available = False
                return

        self._attr_available = True

        try:
            device_url = self.device.url("/")
        except plexapi.exceptions.BadRequest:
            device_url = "127.0.0.1"
        if "127.0.0.1" in device_url:
            self.device.proxyThroughServer()
        self._device_protocol_capabilities = self.device.protocolCapabilities

        for device in filter(None, [self.device, self.session_device]):
            self.device_make = self.device_make or device.device
            self.device_platform = self.device_platform or device.platform
            self.device_product = self.device_product or device.product
            self.device_title = self.device_title or device.title
            self.device_version = self.device_version or device.version

        name_parts = [self.device_product, self.device_title or self.device_platform]
        if (self.device_product in COMMON_PLAYERS) and self.device_make:
            # Add more context in name for likely duplicates
            name_parts.append(self.device_make)
        if self.username and self.username != self.plex_server.owner:
            # Prepend username for shared/managed clients
            name_parts.insert(0, self.username)
        self._attr_name = NAME_FORMAT.format(" - ".join(name_parts))

    def force_idle(self):
        """Force client to idle."""
        self._attr_state = MediaPlayerState.IDLE
        if self.player_source == "session":
            self.device = None
            self.session_device = None
            self._attr_available = False

    @property
    def session(self):
        """Return the active session for this player."""
        return self._session

    @session.setter
    def session(self, session):
        self._session = session
        if session:
            self.session_device = self.session.player
            self.update_state(self.session.state)
        else:
            self._attr_state = MediaPlayerState.IDLE

    @property
    @needs_session
    def username(self):
        """Return the username of the client owner."""
        return self.session.username

    def update_state(self, state):
        """Set the state of the device, handle session termination."""
        if state == "playing":
            self._attr_state = MediaPlayerState.PLAYING
        elif state == "paused":
            self._attr_state = MediaPlayerState.PAUSED
        elif state == "stopped":
            self.session = None
            self.force_idle()
        else:
            self._attr_state = MediaPlayerState.IDLE

    @property
    def _is_player_active(self):
        """Report if the client is playing media."""
        return self.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}

    @property
    def _active_media_plexapi_type(self):
        """Get the active media type required by PlexAPI commands."""
        if self.media_content_type == MediaType.MUSIC:
            return "music"

        return "video"

    @property
    @needs_session
    def session_key(self):
        """Return current session key."""
        return self.session.sessionKey

    @property
    @needs_session
    def media_library_title(self):
        """Return the library name of playing media."""
        return self.session.media_library_title

    @property
    @needs_session
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self.session.media_content_id

    @property
    @needs_session
    def media_content_type(self):
        """Return the content type of current playing media."""
        return self.session.media_content_type

    @property
    @needs_session
    def media_content_rating(self):
        """Return the content rating of current playing media."""
        return self.session.media_content_rating

    @property
    @needs_session
    def media_artist(self):
        """Return the artist of current playing media, music track only."""
        return self.session.media_artist

    @property
    @needs_session
    def media_album_name(self):
        """Return the album name of current playing media, music track only."""
        return self.session.media_album_name

    @property
    @needs_session
    def media_album_artist(self):
        """Return the album artist of current playing media, music only."""
        return self.session.media_album_artist

    @property
    @needs_session
    def media_track(self):
        """Return the track number of current playing media, music only."""
        return self.session.media_track

    @property
    @needs_session
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self.session.media_duration

    @property
    @needs_session
    def media_position(self):
        """Return the duration of current playing media in seconds."""
        return self.session.media_position

    @property
    @needs_session
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self.session.media_position_updated_at

    @property
    @needs_session
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return self.session.media_image_url

    @property
    @needs_session
    def media_summary(self):
        """Return the summary of current playing media."""
        return self.session.media_summary

    @property
    @needs_session
    def media_title(self):
        """Return the title of current playing media."""
        return self.session.media_title

    @property
    @needs_session
    def media_season(self):
        """Return the season of current playing media (TV Show only)."""
        return self.session.media_season

    @property
    @needs_session
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self.session.media_series_title

    @property
    @needs_session
    def media_episode(self):
        """Return the episode of current playing media (TV Show only)."""
        return self.session.media_episode

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self.device and "playback" in self._device_protocol_capabilities:
            return (
                MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.SEEK
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.BROWSE_MEDIA
            )

        return (
            MediaPlayerEntityFeature.BROWSE_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.setVolume(int(volume * 100), self._active_media_plexapi_type)
            self._volume_level = volume  # store since we can't retrieve

    @property
    def volume_level(self):
        """Return the volume level of the client (0..1)."""
        if (
            self._is_player_active
            and self.device
            and "playback" in self._device_protocol_capabilities
        ):
            return self._volume_level
        return None

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if self._is_player_active and self.device:
            return self._volume_muted
        return None

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume.

        Since we can't actually mute, we'll:
        - On mute, store volume and set volume to 0
        - On unmute, set volume to previously stored volume
        """
        if not (self.device and "playback" in self._device_protocol_capabilities):
            return

        self._volume_muted = mute
        if mute:
            self._previous_volume_level = self._volume_level
            self.set_volume_level(0)
        else:
            self.set_volume_level(self._previous_volume_level)

    def media_play(self) -> None:
        """Send play command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.play(self._active_media_plexapi_type)

    def media_pause(self) -> None:
        """Send pause command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.pause(self._active_media_plexapi_type)

    def media_stop(self) -> None:
        """Send stop command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.stop(self._active_media_plexapi_type)

    def media_seek(self, position: float) -> None:
        """Send the seek command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.seekTo(position * 1000, self._active_media_plexapi_type)

    def media_next_track(self) -> None:
        """Send next track command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self) -> None:
        """Send previous track command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.skipPrevious(self._active_media_plexapi_type)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if not (self.device and "playback" in self._device_protocol_capabilities):
            raise HomeAssistantError(
                f"Client is not currently accepting playback controls: {self.name}"
            )

        result = process_plex_payload(
            self.hass, media_type, media_id, default_plex_server=self.plex_server
        )
        _LOGGER.debug("Attempting to play %s on %s", result.media, self.name)

        try:
            self.device.playMedia(result.media, offset=result.offset)
        except requests.exceptions.ConnectTimeout as exc:
            raise HomeAssistantError(
                f"Request failed when playing on {self.name}"
            ) from exc

    @property
    def extra_state_attributes(self):
        """Return the scene state attributes."""
        attributes = {}
        for attr in (
            "media_content_rating",
            "media_library_title",
            "player_source",
            "media_summary",
            "username",
        ):
            if value := getattr(self, attr, None):
                attributes[attr] = value

        return attributes

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        if self.machine_identifier is None:
            return None

        if self.device_product in TRANSIENT_DEVICE_MODELS:
            return DeviceInfo(
                identifiers={(DOMAIN, "plex.tv-clients")},
                name="Plex Client Service",
                manufacturer="Plex",
                model="Plex Clients",
                entry_type=DeviceEntryType.SERVICE,
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self.machine_identifier)},
            manufacturer=self.device_platform or "Plex",
            model=self.device_product or self.device_make,
            # Instead of setting the device name to the entity name, plex
            # should be updated to set has_entity_name = True, and set the entity
            # name to None
            name=cast(str | None, self.name),
            sw_version=self.device_version,
            via_device=(DOMAIN, self.plex_server.machine_identifier),
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        is_internal = is_internal_request(self.hass)
        return await self.hass.async_add_executor_job(
            browse_media,
            self.hass,
            is_internal,
            media_content_type,
            media_content_id,
        )
