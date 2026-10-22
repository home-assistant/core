"""Base entity for LoRaWAN integrations."""

from typing import override

from lorawan_connection import Device

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class LoRaWANEntity[DeviceT: Device](CoordinatorEntity[DataUpdateCoordinator[DeviceT]]):
    """Share model updates; the device manager owns registry cleanup."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[DeviceT],
        description: EntityDescription,
    ) -> None:
        """Represent a device datapoint with a stable unique ID."""
        super().__init__(coordinator)
        self.entity_description = description
        descriptor = self.device.descriptor
        self._attr_unique_id = (
            f"{descriptor.network_id}:{descriptor.dev_eui}:{description.key}"
        )

    @property
    def device(self) -> DeviceT:
        """Return the model shared by this device's entities."""
        return self.coordinator.data

    @property
    @override
    def available(self) -> bool:
        return super().available and not self.device.closed

    @override
    async def async_update(self) -> None:
        """Make update_entity a no-op; values arrive through the subscription."""
