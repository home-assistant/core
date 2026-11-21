"""Base entities for Besen."""

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import NAME
from .coordinator import BesenCoordinator


class BesenEntity(CoordinatorEntity[BesenCoordinator]):
    """Base class for Besen entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BesenCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}_{key}"
        self._attr_translation_key = key
        data = self.coordinator.data
        info = data.info
        name = data.config.device_name or info.advertised_name or info.model or NAME
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, info.address)},
            name=name,
            manufacturer=info.manufacturer or "Besen",
            model=info.model,
            serial_number=info.serial,
            hw_version=info.hardware_version,
            sw_version=info.software_version,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""

        data = self.coordinator.data
        return super().available and data.available and data.authenticated
