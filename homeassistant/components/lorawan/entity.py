"""Shared lifecycle for entities backed by LoRaWAN device models."""

from typing import override

from lorawan_connection import Device

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
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
    async def async_added_to_hass(self) -> None:
        # Abort a queued addition if registry removal already retired its model.
        if self.device.closed:
            if self.registry_entry and self.registry_entry.device_id:
                registry = dr.async_get(self.hass)
                if registry.async_get(self.registry_entry.device_id):
                    registry.async_remove_device(self.registry_entry.device_id)
            raise HomeAssistantError("LoRaWAN device was removed during entity setup")
        await super().async_added_to_hass()

    @override
    async def async_update(self) -> None:
        """Make update_entity a no-op; values arrive through the subscription."""
