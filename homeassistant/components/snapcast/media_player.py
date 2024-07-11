"""Support for interacting with Snapcast clients."""

from __future__ import annotations

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


def register_services():
    """Register snapcast services."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_SNAPSHOT, {}, "snapshot")
    platform.async_register_entity_service(SERVICE_RESTORE, {}, "async_restore")
    platform.async_register_entity_service(
        SERVICE_JOIN, {vol.Required(ATTR_MASTER): cv.entity_id}, handle_async_join
    )
    platform.async_register_entity_service(SERVICE_UNJOIN, {}, handle_async_unjoin)
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


async def handle_async_join(entity, service_call):
    """Handle the entity service join."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Entity is not a client. Can only join clients.")
    await entity.async_join(service_call.data[ATTR_MASTER])


async def handle_async_unjoin(entity, service_call):
    """Handle the entity service unjoin."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Entity is not a client. Can only unjoin clients.")
    await entity.async_unjoin()


async def handle_set_latency(entity, service_call):
    """Handle the entity service set_latency."""
    if not isinstance(entity, SnapcastClientDevice):
        raise TypeError("Latency can only be set for a Snapcast client.")
    await entity.async_set_latency(service_call.data[ATTR_LATENCY])


class SnapcastGroupDevice(MediaPlayerEntity):
    """Representation of a Snapcast group device."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, group, uid_part, entry_id):
        """Initialize the Snapcast group device."""
        self._attr_available = True
        self._group = group
        self._entry_id = entry_id
        self._attr_unique_id = f"{GROUP_PREFIX}{uid_part}_{self._group.identifier}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to group events."""
        self._group.set_callback(self.schedule_update_ha_state)
        self.hass.data[DOMAIN][self._entry_id].groups.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect group object when removed."""
        self._group.set_callback(None)
        self.hass.data[DOMAIN][self._entry_id].groups.remove(self)

    def set_availability(self, available: bool) -> None:
        """Set availability of group."""
        self._attr_available = available
        self.schedule_update_ha_state()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        if self.is_volume_muted:
            return MediaPlayerState.IDLE
        return STREAM_STATUS.get(self._group.stream_status)

    @property
    def identifier(self):
        """Return the snapcast identifier."""
        return self._group.identifier

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._group.friendly_name} {GROUP_SUFFIX}"

    @property
    def source(self):
        """Return the current input source."""
        return self._group.stream

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._group.volume / 100

    @property
    def is_volume_muted(self):
        """Volume muted."""
        return self._group.muted

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._group.streams_by_name().keys())

    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        streams = self._group.streams_by_name()
        if source in streams:
            await self._group.set_stream(streams[source].identifier)
            self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        await self._group.set_muted(mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self._group.set_volume(round(volume * 100))
        self.async_write_ha_state()

    def snapshot(self):
        """Snapshot the group state."""
        self._group.snapshot()

    async def async_restore(self):
        """Restore the group state."""
        await self._group.restore()
        self.async_write_ha_state()


class SnapcastClientDevice(MediaPlayerEntity):
    """Representation of a Snapcast client device."""

    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, client, uid_part, entry_id):
        """Initialize the Snapcast client device."""
        self._attr_available = True
        self._client = client
        # Note: Host part is needed, when using multiple snapservers
        self._attr_unique_id = f"{CLIENT_PREFIX}{uid_part}_{self._client.identifier}"
        self._entry_id = entry_id

    async def async_added_to_hass(self) -> None:
        """Subscribe to client events."""
        self._client.set_callback(self.schedule_update_ha_state)
        self.hass.data[DOMAIN][self._entry_id].clients.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect client object when removed."""
        self._client.set_callback(None)
        self.hass.data[DOMAIN][self._entry_id].clients.remove(self)

    def set_availability(self, available: bool) -> None:
        """Set availability of group."""
        self._attr_available = available
        self.schedule_update_ha_state()

    @property
    def identifier(self):
        """Return the snapcast identifier."""
        return self._client.identifier

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._client.friendly_name} {CLIENT_SUFFIX}"

    @property
    def source(self):
        """Return the current input source."""
        return self._client.group.stream

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._client.volume / 100

    @property
    def is_volume_muted(self):
        """Volume muted."""
        return self._client.muted

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._client.group.streams_by_name().keys())

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the player."""
        if self._client.connected:
            if self.is_volume_muted or self._client.group.muted:
                return MediaPlayerState.IDLE
            return STREAM_STATUS.get(self._client.group.stream_status)
        return MediaPlayerState.STANDBY

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        state_attrs = {}
        if self.latency is not None:
            state_attrs["latency"] = self.latency
        return state_attrs

    @property
    def latency(self):
        """Latency for Client."""
        return self._client.latency

    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        streams = self._client.group.streams_by_name()
        if source in streams:
            await self._client.group.set_stream(streams[source].identifier)
            self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        await self._client.set_muted(mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self._client.set_volume(round(volume * 100))
        self.async_write_ha_state()

    async def async_join(self, master):
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
            for group in self._client.groups_available()
            if master_entity.identifier in group.clients
        )
        await master_group.add_client(self._client.identifier)
        self.async_write_ha_state()

    async def async_unjoin(self):
        """Unjoin the group the player is currently in."""
        await self._client.group.remove_client(self._client.identifier)
        self.async_write_ha_state()

    def snapshot(self):
        """Snapshot the client state."""
        self._client.snapshot()

    async def async_restore(self):
        """Restore the client state."""
        await self._client.restore()
        self.async_write_ha_state()

    async def async_set_latency(self, latency):
        """Set the latency of the client."""
        await self._client.set_latency(latency)
        self.async_write_ha_state()
