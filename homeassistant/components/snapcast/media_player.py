"""Support for interacting with Snapcast clients."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.server import Snapserver
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
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

STREAM_STATUS = {
    "idle": MediaPlayerState.IDLE,
    "playing": MediaPlayerState.PLAYING,
    "unknown": None,
}


def register_services() -> None:
    """Register snapcast services."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_SNAPSHOT, None, "snapshot")
    platform.async_register_entity_service(SERVICE_RESTORE, None, "async_restore")
    platform.async_register_entity_service(
        SERVICE_JOIN, {vol.Required(ATTR_MASTER): cv.entity_id}, handle_async_join
    )
    platform.async_register_entity_service(SERVICE_UNJOIN, None, handle_async_unjoin)
    platform.async_register_entity_service(
        SERVICE_SET_LATENCY,
        {vol.Required(ATTR_LATENCY): cv.positive_int},
        handle_set_latency,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the snapcast config entry."""
    snapcast_server: Snapserver = hass.data[DOMAIN][config_entry.entry_id].server

    register_services()

    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    hpid = f"{host}:{port}"

    groups: list[MediaPlayerEntity] = [
        SnapcastGroupDevice(group, hpid, config_entry.entry_id)
        for group in snapcast_server.groups
    ]
    clients: list[MediaPlayerEntity] = [
        SnapcastClientDevice(client, hpid, config_entry.entry_id)
        for client in snapcast_server.clients
    ]
    async_add_entities(clients + groups)
    hass.data[DOMAIN][
        config_entry.entry_id
    ].hass_async_add_entities = async_add_entities


async def handle_async_join(entity, service_call) -> None:
    """Handle the entity service join."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Entity is not a client. Can only join clients.")
    await entity.async_join(service_call.data[ATTR_MASTER])


async def handle_async_unjoin(entity, service_call) -> None:
    """Handle the entity service unjoin."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Entity is not a client. Can only unjoin clients.")
    await entity.async_unjoin()


async def handle_set_latency(entity, service_call) -> None:
    """Handle the entity service set_latency."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Latency can only be set for a Snapcast client.")
    await entity.async_set_latency(service_call.data[ATTR_LATENCY])


class SnapcastBaseDevice(MediaPlayerEntity):
    """Base class representing a Snapcast device."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        device: Snapgroup | Snapclient,
        entry_id: str,
    ) -> None:
        """Initialize the base device."""
        self._attr_available = True
        self._device = device
        self._entry_id = entry_id

    def _append(self) -> None:
        """Add self to appropriate list."""
        raise NotImplementedError

    def _remove(self) -> None:
        """Remove self from appropriate list."""
        raise NotImplementedError

    @property
    def current_group(self) -> Snapgroup:
        """Return the group."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        self._device.set_callback(self.schedule_update_ha_state)
        self._append()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self._device.set_callback(None)
        self._remove()

    def set_availability(self, available: bool) -> None:
        """Set availability of device."""
        self._attr_available = available
        self.schedule_update_ha_state()

    @property
    def identifier(self) -> str:
        """Return the snapcast identifier."""
        return self._device.identifier

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.current_group.stream

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return list(self.current_group.streams_by_name().keys())

    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        streams = self.current_group.streams_by_name()
        if source in streams:
            await self.current_group.set_stream(streams[source].identifier)
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
    def volume_level(self) -> float | None:
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


class SnapcastGroupDevice(SnapcastBaseDevice):
    """Representation of a Snapcast group device."""

    def __init__(
        self,
        group: Snapgroup,
        uid_part: str,
        entry_id: str,
    ) -> None:
        """Initialize the Snapcast group device."""
        super().__init__(group, entry_id)
        self._attr_unique_id = (
            f"{GROUP_PREFIX}{uid_part}_{self.current_group.identifier}"
        )

    def _append(self) -> None:
        """Add self to group list."""
        self.hass.data[DOMAIN][self._entry_id].groups.append(self)

    def _remove(self) -> None:
        """Remove self from group list."""
        self.hass.data[DOMAIN][self._entry_id].groups.remove(self)

    @property
    def current_group(self) -> Snapgroup:
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


class SnapcastClientDevice(SnapcastBaseDevice):
    """Representation of a Snapcast client device."""

    def __init__(
        self,
        client: Snapclient,
        uid_part: str,
        entry_id: str,
    ) -> None:
        """Initialize the Snapcast client device."""
        super().__init__(client, entry_id)
        # Note: Host part is needed, when using multiple snapservers
        self._attr_unique_id = f"{CLIENT_PREFIX}{uid_part}_{self._device.identifier}"

    def _append(self) -> None:
        """Add self to client list."""
        self.hass.data[DOMAIN][self._entry_id].clients.append(self)

    def _remove(self) -> None:
        """Remove self from client list."""
        self.hass.data[DOMAIN][self._entry_id].clients.remove(self)

    @property
    def current_group(self) -> Snapgroup:
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
            if self.is_volume_muted or self.current_group.muted:
                return MediaPlayerState.IDLE
            return STREAM_STATUS.get(self.current_group.stream_status)
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
        master_entity = next(
            entity
            for entity in self.hass.data[DOMAIN][self._entry_id].clients
            if entity.entity_id == master
        )
        if not isinstance(master_entity, SnapcastClientDevice):
            raise TypeError("Master is not a client device. Can only join clients.")

        master_group = next(
            group
            for group in self._device.groups_available()
            if master_entity.identifier in group.clients
        )
        await master_group.add_client(self._device.identifier)
        self.async_write_ha_state()

    async def async_unjoin(self) -> None:
        """Unjoin the group the player is currently in."""
        await self.current_group.remove_client(self._device.identifier)
        self.async_write_ha_state()
