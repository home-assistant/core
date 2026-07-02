"""Base entities for Besen BS20."""

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import BesenBS20Coordinator


class BesenBS20Entity(CoordinatorEntity[BesenBS20Coordinator]):
    """Base class for Besen BS20 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BesenBS20Coordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}_{key}"
        self._attr_translation_key = key
        data = self.coordinator.data or self.coordinator.client.state
        info = data.info
        name = data.config.device_name or info.advertised_name or info.model or NAME
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.address)},
            connections={(dr.CONNECTION_BLUETOOTH, info.address)},
            name=name,
            manufacturer=info.manufacturer or "Besen",
            model=info.model or "BS20",
            serial_number=info.serial,
            hw_version=info.hardware_version,
            sw_version=info.software_version,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""

        data = self.coordinator.data or self.coordinator.client.state
        return super().available and data.available and data.authenticated
