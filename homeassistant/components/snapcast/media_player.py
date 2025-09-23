"""Support for interacting with Snapcast clients."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
import voluptuous as vol

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
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_LATENCY,
    ATTR_MASTER,
    CLIENT_PREFIX,
    CLIENT_SUFFIX,
    DOMAIN,
    GROUP_PREFIX,
    GROUP_SUFFIX,
    SERVICE_JOIN,
    SERVICE_RESTORE,
    SERVICE_SET_LATENCY,
    SERVICE_SNAPSHOT,
    SERVICE_UNJOIN,
)
from .coordinator import SnapcastUpdateCoordinator
from .entity import SnapcastCoordinatorEntity

STREAM_STATUS = {
    "idle": MediaPlayerState.IDLE,
    "playing": MediaPlayerState.PLAYING,
    "unknown": None,
}

_SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

_LOGGER = logging.getLogger(__name__)


def register_services() -> None:
    """Register snapcast services."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_SNAPSHOT, None, "snapshot")
    platform.async_register_entity_service(SERVICE_RESTORE, None, "async_restore")
    platform.async_register_entity_service(
        SERVICE_JOIN, {vol.Required(ATTR_MASTER): cv.entity_id}, "async_join"
    )
    platform.async_register_entity_service(SERVICE_UNJOIN, None, "async_unjoin")
    platform.async_register_entity_service(
        SERVICE_SET_LATENCY,
        {vol.Required(ATTR_LATENCY): cv.positive_int},
        "async_set_latency",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the snapcast config entry."""

    # Fetch coordinator from global data
    coordinator: SnapcastUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    register_services()

    _known_group_ids: set[str] = set()
    _known_client_ids: set[str] = set()

    @callback
    def _update_entities(
        entity_class: type[SnapcastClientDevice | SnapcastGroupDevice],
        known_ids: set[str],
        get_device: Callable[[str], Snapclient | Snapgroup],
        get_devices: Callable[[], list[Snapclient] | list[Snapgroup]],
    ) -> None:
        # Get IDs of current devices on server
        snapcast_ids = {d.identifier for d in get_devices()}

        # Update known IDs
        ids_to_add = snapcast_ids - known_ids
        ids_to_remove = known_ids - snapcast_ids

        known_ids.difference_update(ids_to_remove)
        known_ids.update(ids_to_add)

        # Exit early if no changes
        if not (ids_to_add | ids_to_remove):
            return

        _LOGGER.debug(
            "New %s: %s",
            entity_class,
            str([get_device(d).friendly_name for d in ids_to_add]),
        )
        _LOGGER.debug(
            "Remove %s IDs: %s",
            entity_class,
            str([list(ids_to_remove)]),
        )

        # Add new entities
        async_add_entities(
            [
                entity_class(coordinator, get_device(snapcast_id))
                for snapcast_id in ids_to_add
            ]
        )

        # Remove stale entities
        entity_registry = er.async_get(hass)
        for snapcast_id in ids_to_remove:
            if entity_id := entity_registry.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN,
                DOMAIN,
                entity_class.get_unique_id(coordinator.host_id, snapcast_id),
            ):
                entity_registry.async_remove(entity_id)

    def _update_clients() -> None:
        _update_entities(
            SnapcastClientDevice,
            _known_client_ids,
            coordinator.server.client,
            lambda: coordinator.server.clients,
        )

    # Create client entities and add listener to update clients on server update
    _update_clients()
    coordinator.async_add_listener(_update_clients)

    def _update_groups() -> None:
        _update_entities(
            SnapcastGroupDevice,
            _known_group_ids,
            coordinator.server.group,
            lambda: coordinator.server.groups,
        )

    # Create group entities and add listener to update groups on server update
    _update_groups()
    coordinator.async_add_listener(_update_groups)


class SnapcastBaseDevice(SnapcastCoordinatorEntity, MediaPlayerEntity):
    """Base class representing a Snapcast device."""

    _attr_should_poll = False
    _attr_supported_features = _SUPPORTED_FEATURES
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        coordinator: SnapcastUpdateCoordinator,
        device: Snapgroup | Snapclient,
    ) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = self.get_unique_id(
            coordinator.host_id, device.identifier
        )

    @classmethod
    def get_unique_id(cls, host, id) -> str:
        """Build a unique ID."""
        raise NotImplementedError

    @property
    def _current_group(self) -> Snapgroup:
        """Return the group."""
        raise NotImplementedError

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

    def snapshot(self) -> None:
        """Snapshot the group state."""
        self._device.snapshot()

    async def async_restore(self) -> None:
        """Restore the group state."""
        await self._device.restore()
        self.async_write_ha_state()

    async def async_set_latency(self, latency) -> None:
        """Handle the set_latency service."""
        raise NotImplementedError

    async def async_join(self, master) -> None:
        """Handle the join service."""
        raise NotImplementedError

    async def async_unjoin(self) -> None:
        """Handle the unjoin service."""
        raise NotImplementedError

    def _async_create_grouping_deprecation_issue(self) -> None:
        """Create an issue for deprecated grouping actions."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_grouping_actions",
            breaks_in_ha_version="2026.2.0",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_grouping_actions",
        )

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


class SnapcastGroupDevice(SnapcastBaseDevice):
    """Representation of a Snapcast group device."""

    _device: Snapgroup

    @classmethod
    def get_unique_id(cls, host, id) -> str:
        """Get a unique ID for a group."""
        return f"{GROUP_PREFIX}{host}_{id}"

    @property
    def _current_group(self) -> Snapgroup:
        """Return the group."""
        return self._device

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self._device.friendly_name} {GROUP_SUFFIX}"

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        if self.is_volume_muted:
            return MediaPlayerState.IDLE
        return STREAM_STATUS.get(self._device.stream_status)

    async def async_set_latency(self, latency) -> None:
        """Handle the set_latency service."""
        raise ServiceValidationError("Latency can only be set for a Snapcast client.")

    async def async_join(self, master) -> None:
        """Handle the join service."""
        raise ServiceValidationError("Entity is not a client. Can only join clients.")

    async def async_unjoin(self) -> None:
        """Handle the unjoin service."""
        raise ServiceValidationError("Entity is not a client. Can only unjoin clients.")

    def _async_create_group_deprecation_issue(self) -> None:
        """Create an issue for deprecated group entities."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_group_entities",
            breaks_in_ha_version="2026.2.0",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_group_entities",
        )

    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        # Groups are deprecated, create an issue when used
        self._async_create_group_deprecation_issue()

        await super().async_select_source(source)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        # Groups are deprecated, create an issue when used
        self._async_create_group_deprecation_issue()

        await super().async_mute_volume(mute)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        # Groups are deprecated, create an issue when used
        self._async_create_group_deprecation_issue()

        await super().async_set_volume_level(volume)

    def snapshot(self) -> None:
        """Snapshot the group state."""
        # Groups are deprecated, create an issue when used
        self._async_create_group_deprecation_issue()

        super().snapshot()

    async def async_restore(self) -> None:
        """Restore the group state."""
        # Groups are deprecated, create an issue when used
        self._async_create_group_deprecation_issue()

        await super().async_restore()


class SnapcastClientDevice(SnapcastBaseDevice):
    """Representation of a Snapcast client device."""

    _device: Snapclient
    _attr_supported_features = (
        _SUPPORTED_FEATURES | MediaPlayerEntityFeature.GROUPING
    )  # Clients support grouping

    @classmethod
    def get_unique_id(cls, host, id) -> str:
        """Get a unique ID for a client."""
        return f"{CLIENT_PREFIX}{host}_{id}"

    @property
    def _current_group(self) -> Snapgroup:
        """Return the group the client is associated with."""
        return self._device.group

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
        """Latency for Client."""
        return self._device.latency

    async def async_set_latency(self, latency) -> None:
        """Set the latency of the client."""
        await self._device.set_latency(latency)
        self.async_write_ha_state()

    async def async_join(self, master) -> None:
        """Join the group of the master player."""
        # Action is deprecated, create an issue
        self._async_create_grouping_deprecation_issue()

        entity_registry = er.async_get(self.hass)
        master_entity = entity_registry.async_get(master)
        if master_entity is None:
            raise ServiceValidationError(f"Master entity '{master}' not found.")

        # Validate master entity is a client
        unique_id = master_entity.unique_id
        if not unique_id.startswith(CLIENT_PREFIX):
            raise ServiceValidationError(
                "Master is not a client device. Can only join clients."
            )

        # Extract the client ID and locate it's group
        identifier = unique_id.split("_")[-1]
        master_group = next(
            group
            for group in self._device.groups_available()
            if identifier in group.clients
        )
        await master_group.add_client(self._device.identifier)
        self.async_write_ha_state()

    async def async_unjoin(self) -> None:
        """Unjoin the group the player is currently in."""
        # Action is deprecated, create an issue
        self._async_create_grouping_deprecation_issue()

        await self._current_group.remove_client(self._device.identifier)
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
