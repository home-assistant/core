"""Support for interacting with Snapcast clients."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CLIENT_PREFIX, CLIENT_SUFFIX, DOMAIN
from .coordinator import SnapcastUpdateCoordinator
from .entity import SnapcastCoordinatorEntity

STREAM_STATUS = {
    "idle": MediaPlayerState.IDLE,
    "playing": MediaPlayerState.PLAYING,
    "unknown": None,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the snapcast config entry."""

    # Fetch coordinator from global data
    coordinator: SnapcastUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    _known_client_ids: set[str] = set()

    @callback
    def _update_clients() -> None:
        # Get IDs of current clients on server
        snapcast_ids = {d.identifier for d in coordinator.server.clients}

        # Update known IDs
        ids_to_add = snapcast_ids - _known_client_ids
        ids_to_remove = _known_client_ids - snapcast_ids

        _known_client_ids.difference_update(ids_to_remove)
        _known_client_ids.update(ids_to_add)

        # Exit early if no changes
        if not (ids_to_add | ids_to_remove):
            return

        _LOGGER.debug(
            "New snapcast client: %s",
            str([coordinator.server.client(d).friendly_name for d in ids_to_add]),
        )
        _LOGGER.debug(
            "Remove snapcast client IDs: %s",
            str([list(ids_to_remove)]),
        )

        # Add new entities
        async_add_entities(
            [
                SnapcastClientDevice(
                    coordinator, coordinator.server.client(snapcast_id)
                )
                for snapcast_id in ids_to_add
            ]
        )

        # Remove stale entities
        entity_registry = er.async_get(hass)
        for snapcast_id in ids_to_remove:
            if entity_id := entity_registry.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN,
                DOMAIN,
                SnapcastClientDevice.get_unique_id(coordinator.host_id, snapcast_id),
            ):
                entity_registry.async_remove(entity_id)

    # Create client entities and add listener to update clients on server update
    _update_clients()
    coordinator.async_add_listener(_update_clients)


class SnapcastClientDevice(SnapcastCoordinatorEntity, MediaPlayerEntity):
    """Representation of a Snapcast client device."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.GROUPING
    )
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _device: Snapclient

    def __init__(
        self,
        coordinator: SnapcastUpdateCoordinator,
        device: Snapclient,
    ) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = self.get_unique_id(
            coordinator.host_id, device.identifier
        )

    @classmethod
    def get_unique_id(cls, host, id) -> str:
        """Get a unique ID for a client."""
        return f"{CLIENT_PREFIX}{host}_{id}"

    @property
    def _current_group(self) -> Snapgroup:
        """Return the group the client is associated with."""
        return self._device.group

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        await super().async_added_to_hass()
        self._device.set_callback(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self._device.set_callback(None)

    @property
    def identifier(self) -> str:
        """Return the snapcast identifier."""
        return self._device.identifier

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self._device.friendly_name} {CLIENT_SUFFIX}"

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        if self._device.connected:
            if self.is_volume_muted or self._current_group.muted:
                return MediaPlayerState.IDLE
            return STREAM_STATUS.get(self._current_group.stream_status)
        return MediaPlayerState.OFF

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        state_attrs = {}
        if self.latency is not None:
            state_attrs["latency"] = self.latency
        return state_attrs

    @property
    def latency(self) -> float | None:
        """Return current latency."""
        return self._device.latency

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._current_group.stream

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return list(self._current_group.streams_by_name().keys())

    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        streams = self._current_group.streams_by_name()
        if source in streams:
            await self._current_group.set_stream(streams[source].identifier)
            self.async_write_ha_state()

    @property
    def is_volume_muted(self) -> bool:
        """Volume muted."""
        return self._device.muted

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        await self._device.set_muted(mute)
        self.async_write_ha_state()

    @property
    def volume_level(self) -> float:
        """Return the volume level."""
        return self._device.volume / 100

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self._device.set_volume(round(volume * 100))
        self.async_write_ha_state()

    async def async_snapshot(self) -> None:
        """Snapshot the group state."""
        self._device.snapshot()

    async def async_restore(self) -> None:
        """Restore the group state."""
        await self._device.restore()
        self.async_write_ha_state()

    async def async_set_latency(self, latency) -> None:
        """Set the latency of the client."""
        await self._device.set_latency(latency)
        self.async_write_ha_state()

    @property
    def group_members(self) -> list[str] | None:
        """List of player entities which are currently grouped together for synchronous playback."""
        entity_registry = er.async_get(self.hass)
        return [
            entity_id
            for client_id in self._current_group.clients
            if (
                entity_id := entity_registry.async_get_entity_id(
                    MEDIA_PLAYER_DOMAIN,
                    DOMAIN,
                    self.get_unique_id(self.coordinator.host_id, client_id),
                )
            )
        ]

    async def async_join_players(self, group_members: list[str]) -> None:
        """Add `group_members` to this client's current group."""
        # Get the client entity for each group member excluding self
        entity_registry = er.async_get(self.hass)
        clients = [
            entity
            for entity_id in group_members
            if (entity := entity_registry.async_get(entity_id))
            and entity.unique_id != self.unique_id
        ]

        for client in clients:
            # Valid entity is a snapcast client
            if not client.unique_id.startswith(CLIENT_PREFIX):
                raise ServiceValidationError(
                    f"Entity '{client.entity_id}' is not a Snapcast client device."
                )

            # Extract client ID and join it to the current group
            identifier = client.unique_id.split("_")[-1]
            await self._current_group.add_client(identifier)

        self.async_write_ha_state()

    async def async_unjoin_player(self) -> None:
        """Remove this client from it's current group."""
        await self._current_group.remove_client(self._device.identifier)
        self.async_write_ha_state()

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Get metadata from the current stream."""
        if metadata := self.coordinator.server.stream(
            self._current_group.stream
        ).metadata:
            return metadata

        # Fallback to an empty dict
        return {}

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.metadata.get("title")

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.metadata.get("artUrl")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if (value := self.metadata.get("artist")) is not None:
            return ", ".join(value)

        return None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.metadata.get("album")

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        if (value := self.metadata.get("albumArtist")) is not None:
            return ", ".join(value)

        return None

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        if (value := self.metadata.get("trackNumber")) is not None:
            return int(value)

        return None

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if (value := self.metadata.get("duration")) is not None:
            return int(value)

        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        # Position is part of properties object, not metadata object
        if properties := self.coordinator.server.stream(
            self._current_group.stream
        ).properties:
            if (value := properties.get("position")) is not None:
                return int(value)

        return None
