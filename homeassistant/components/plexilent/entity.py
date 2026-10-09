"""Base entity for the Plexilent integration."""

from collections.abc import Callable
from typing import Any, override

from pyplexilent import Device, PlexilentError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlexilentConfigEntry, PlexilentCoordinator


class PlexilentEntity(CoordinatorEntity[PlexilentCoordinator]):
    """A device of the account; the entity is the device itself."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: PlexilentCoordinator, device_id: str) -> None:
        """Initialize the entity for one device."""
        super().__init__(coordinator)
        self._id = device_id
        device = self.device
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="Plexilent",
            model=device.type,
            suggested_area=device.room,
        )

    @property
    def device(self) -> Device:
        """Return the device's last known state."""
        return self.coordinator.data[self._id]

    @property
    @override
    def available(self) -> bool:
        """Return whether the cloud lists the device and its gateway reaches it."""
        return (
            super().available
            and self._id in self.coordinator.data
            and self.device.online
        )

    async def _send(self, **fields: Any) -> None:
        """Command the device; its answer is the new state until the next poll."""
        try:
            device = await self.coordinator.client.command(self._id, **fields)
        except PlexilentError as err:
            raise HomeAssistantError(
                f"Could not control {self.device.name}: {err}"
            ) from err
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, self._id: device}
        )


def add_entities(
    entry: PlexilentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    types: set[str],
    factory: Callable[[PlexilentCoordinator, str], PlexilentEntity],
) -> None:
    """Add an entity per device of these types, now and whenever one is added."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    def add() -> None:
        new = [
            device_id
            for device_id, device in coordinator.data.items()
            if device.type in types and device_id not in known
        ]
        known.update(new)
        if new:
            async_add_entities(factory(coordinator, device_id) for device_id in new)

    add()
    entry.async_on_unload(coordinator.async_add_listener(add))
