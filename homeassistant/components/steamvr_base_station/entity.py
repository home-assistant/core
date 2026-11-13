"""Base entity for SteamVR Base Station."""

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription

from .coordinator import SteamVRBaseStationCoordinator


class SteamVRBaseStationEntity(
    PassiveBluetoothCoordinatorEntity[SteamVRBaseStationCoordinator]
):
    """An entity belonging to one base station."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SteamVRBaseStationCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        info = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.entry.title,
            manufacturer=coordinator.station.manufacturer,
            model=coordinator.station.product_name,
            model_id=info.model,
            sw_version=info.firmware,
            hw_version=info.hardware,
            serial_number=info.serial,
        )
