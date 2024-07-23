"""Base class for Squeezebox Sensor entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LMSStatusDataUpdateCoordinator


class StatusSensorEntity(CoordinatorEntity[LMSStatusDataUpdateCoordinator]):
    """Defines a base staus sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: DeviceInfo,
        coordinator: LMSStatusDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize status sensor entity."""
        super().__init__(coordinator, context=description.key)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_device_info = device
        self._attr_name = description.key
        self._attr_unique_id = device["serial_number"] + description.key
