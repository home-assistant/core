"""Base entity for Atomberg."""

from typing import Any, override

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AtombergDevice
from .const import DOMAIN
from .coordinator import AtombergCoordinator


class AtombergEntity(CoordinatorEntity[AtombergCoordinator]):
    """Base class for Atomberg entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            connections={(CONNECTION_NETWORK_MAC, device.device_id)},
            manufacturer="Atomberg",
            model=device.model,
            model_id=device.series,
            name=device.name,
        )

    @property
    def device_state(self) -> dict[str, Any]:
        """Return the latest known state of the device."""
        return self.coordinator.data[self.device.device_id]

    @property
    @override
    def available(self) -> bool:
        """Return whether the device is online."""
        return (
            super().available
            and self.device.device_id in self.coordinator.data
            and self.device_state["is_online"]
        )

    async def _async_send(
        self, command: dict[str, Any], new_state: dict[str, Any]
    ) -> None:
        await self.coordinator.async_send_command(
            self.device.device_id, command, new_state
        )
