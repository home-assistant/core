"""Support to interface with the Emby API."""

from __future__ import annotations

from datetime import datetime
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import EmbyConfigEntry
from .const import DEFAULT_HOST, DEFAULT_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

MEDIA_TYPE_TRAILER = "trailer"

SUPPORT_EMBY = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.PLAY
)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Emby platform."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Emby",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmbyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media_player platform from the Emby config entry."""
    async_add_entities(
        EmbyDevice(entry, device_id) for device_id in entry.runtime_data.devices
    )


class EmbyDevice(MediaPlayerEntity):
    """Representation of an Emby device."""

    _attr_should_poll = False

    def __init__(self, entry: EmbyConfigEntry, device_id: str) -> None:
        """Initialize the Emby device."""
        _LOGGER.debug("New Emby Device initialized with ID: %s", device_id)
        self.emby = entry.runtime_data
        self.device_id = device_id
        self.device = self.emby.devices[self.device_id]

        self.media_status_last_position = None
        self.media_status_received = None

        self._attr_unique_id = device_id

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self.emby.add_update_callback(self.async_update_callback, self.device_id)

    @callback
    def async_update_callback(self, msg):
        """Handle device updates."""
        # Check if we should update progress
        if self.device.media_position:
            if self.device.media_position != self.media_status_last_position:
                self.media_status_last_position = self.device.media_position
                self.media_status_received = dt_util.utcnow()
        elif not self.device.is_nowplaying:
            # No position, but we have an old value and are still playing
            self.media_status_last_position = None
            self.media_status_received = None

        self.async_write_ha_state()

    def set_available(self, value: bool) -> None:
        """Set available property."""
        self._attr_available = value

    @property
    def supports_remote_control(self):
        """Return control ability."""
        return self.device.supports_remote_control

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"Emby {self.device.name}" or DEVICE_DEFAULT_NAME

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        state = self.device.state
        if state == "Paused":
            return MediaPlayerState.PAUSED
        if state == "Playing":
            return MediaPlayerState.PLAYING
        if state == "Idle":
            return MediaPlayerState.IDLE
        if state == "Off":
            return MediaPlayerState.OFF
        return None

    @property
    def app_name(self) -> str | None:
        """Return current user as app_name."""
        # Ideally the media_player object would have a user property.
        return self.device.username

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self.device.media_id

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        media_type = self.device.media_type
        if media_type == "Episode":
            return MediaType.TVSHOW
        if media_type == "Movie":
            return MediaType.MOVIE
        if media_type == "Trailer":
            return MEDIA_TYPE_TRAILER
        if media_type == "Music":
            return MediaType.MUSIC
        if media_type == "Video":
            return MediaType.VIDEO
        if media_type == "Audio":
            return MediaType.MUSIC
        if media_type == "TvChannel":
            return MediaType.CHANNEL
        return None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        return self.device.media_runtime

    @property
    def media_position(self) -> int | None:
        """Return the position of current playing media in seconds."""
        return self.media_status_last_position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.media_status_received

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        return self.device.media_image_url

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        return self.device.media_title

    @property
    def media_season(self) -> str | None:
        """Season of current playing media (TV Show only)."""
        return self.device.media_season

    @property
    def media_series_title(self) -> str | None:
        """Return the title of the series of current playing media (TV)."""
        return self.device.media_series_title

    @property
    def media_episode(self) -> str | None:
        """Return the episode of current playing media (TV only)."""
        return self.device.media_episode

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media (Music only)."""
        return self.device.media_album_name

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media (Music track only)."""
        return self.device.media_artist

    @property
    def media_album_artist(self) -> str | None:
        """Return the album artist of current playing media (Music only)."""
        return self.device.media_album_artist

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self.supports_remote_control:
            return SUPPORT_EMBY
        return MediaPlayerEntityFeature(0)

    async def async_media_play(self) -> None:
        """Play media."""
        await self.device.media_play()

    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self.device.media_pause()

    async def async_media_stop(self) -> None:
        """Stop the media player."""
        await self.device.media_stop()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.device.media_next()

    async def async_media_previous_track(self) -> None:
        """Send next track command."""
        await self.device.media_previous()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.device.media_seek(position)
