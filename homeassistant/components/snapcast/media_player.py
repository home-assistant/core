"""Support for interacting with Snapcast clients."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the snapcast config entry."""

    # Fetch coordinator from global data
    coordinator: SnapcastUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create an ID for the Snapserver
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    host_id = f"{host}:{port}"

    register_services()

    _known_group_ids: set[str] = set()
    _known_client_ids: set[str] = set()

    @callback
    def _check_entities() -> None:
        nonlocal _known_group_ids, _known_client_ids

        def _update_known_ids(known_ids, ids) -> tuple[set[str], set[str]]:
            ids_to_add = ids - known_ids
            ids_to_remove = known_ids - ids

            # Update known IDs
            known_ids.difference_update(ids_to_remove)
            known_ids.update(ids_to_add)

            return ids_to_add, ids_to_remove

        group_ids = {g.identifier for g in coordinator.server.groups}
        groups_to_add, groups_to_remove = _update_known_ids(_known_group_ids, group_ids)

        client_ids = {c.identifier for c in coordinator.server.clients}
        clients_to_add, clients_to_remove = _update_known_ids(
            _known_client_ids, client_ids
        )

        # Exit early if no changes
        if not (groups_to_add | groups_to_remove | clients_to_add | clients_to_remove):
            return

        _LOGGER.debug(
            "New clients: %s",
            str([coordinator.server.client(c).friendly_name for c in clients_to_add]),
        )
        _LOGGER.debug(
            "New groups: %s",
            str([coordinator.server.group(g).friendly_name for g in groups_to_add]),
        )
        _LOGGER.debug(
            "Remove client IDs: %s",
            str([list(clients_to_remove)]),
        )
        _LOGGER.debug(
            "Remove group IDs: %s",
            str(list(groups_to_remove)),
        )

        # Add new entities
        async_add_entities(
            [
                SnapcastGroupDevice(
                    coordinator, coordinator.server.group(group_id), host_id
                )
                for group_id in groups_to_add
            ]
            + [
                SnapcastClientDevice(
                    coordinator, coordinator.server.client(client_id), host_id
                )
                for client_id in clients_to_add
            ]
        )

        # Remove stale entities
        entity_registry = er.async_get(hass)
        for group_id in groups_to_remove:
            if entity_id := entity_registry.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN,
                DOMAIN,
                SnapcastGroupDevice.get_unique_id(host_id, group_id),
            ):
                entity_registry.async_remove(entity_id)

        for client_id in clients_to_remove:
            if entity_id := entity_registry.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN,
                DOMAIN,
                SnapcastClientDevice.get_unique_id(host_id, client_id),
            ):
                entity_registry.async_remove(entity_id)

    coordinator.async_add_listener(_check_entities)
    _check_entities()


class SnapcastBaseDevice(SnapcastCoordinatorEntity, MediaPlayerEntity):
    """Base class representing a Snapcast device."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        coordinator: SnapcastUpdateCoordinator,
        device: Snapgroup | Snapclient,
        host_id: str,
    ) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = self.get_unique_id(host_id, device.identifier)

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


class SnapcastClientDevice(SnapcastBaseDevice):
    """Representation of a Snapcast client device."""

    _device: Snapclient

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
        return MediaPlayerState.STANDBY

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
        await self._current_group.remove_client(self._device.identifier)
        self.async_write_ha_state()
