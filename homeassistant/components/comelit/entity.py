"""Base entity for Comelit."""

from __future__ import annotations

from aiocomelit import ComelitSerialBridgeObject

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComelitSerialBridge


class ComelitBridgeBaseEntity(CoordinatorEntity[ComelitSerialBridge]):
    """Comelit Bridge base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init cover entity."""
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, device.type)
