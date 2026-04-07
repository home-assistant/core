"""Support for Jellyfin remote commands."""

from __future__ import annotations

from collections.abc import Iterable
import time
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinClientEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Jellyfin remote from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def handle_coordinator_update() -> None:
        """Add remote per device that supports remote control."""
        entities: list[RemoteEntity] = []
        for device_id, device_info in coordinator.known_devices.items():
            if device_id not in coordinator.device_remote_ids and device_info.get(
                "SupportsRemoteControl", False
            ):
                entity = JellyfinRemote(coordinator, device_id)
                LOGGER.debug("Creating remote for device: %s", device_id)
                coordinator.device_remote_ids.add(device_id)
                entities.append(entity)
        for device_id, device_info in coordinator.ephemeral_devices.items():
            if device_id not in coordinator.device_remote_ids and device_info.get(
                "SupportsRemoteControl", False
            ):
                entity = JellyfinRemote(coordinator, device_id)
                LOGGER.debug("Creating ephemeral remote for device: %s", device_id)
                coordinator.device_remote_ids.add(device_id)
                entities.append(entity)
        async_add_entities(entities)

    handle_coordinator_update()

    entry.async_on_unload(coordinator.async_add_listener(handle_coordinator_update))


class JellyfinRemote(JellyfinClientEntity, RemoteEntity):
    """Defines a Jellyfin remote entity."""

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Jellyfin Remote entity."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = (
            f"{coordinator.server_id}-{coordinator.user_id}-{device_id}"
        )

    @property
    def is_on(self) -> bool:
        """Return True if the device has an active session."""
        session = self.session_data
        return bool(session and session.get("IsActive", False))

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to the client."""
        if (sid := self.session_id) is None:
            raise HomeAssistantError("Device is offline")
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                self.coordinator.api_client.jellyfin.command(sid, single_command)
                time.sleep(delay)
