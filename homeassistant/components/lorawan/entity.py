"""Shared lifecycle for entities backed by LoRaWAN device models."""

from typing import override

from lorawan_connection import Device

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class LoRaWANEntity[DeviceT: Device](CoordinatorEntity[DataUpdateCoordinator[DeviceT]]):
    """Share model updates; the device manager owns registry cleanup."""

    _attr_has_entity_name = True

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
