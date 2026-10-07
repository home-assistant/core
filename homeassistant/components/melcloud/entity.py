"""Base entity for MELCloud integration."""

from typing import override

from pymelcloud.atw_device import Zone

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MelCloudDeviceUpdateCoordinator


class MelCloudEntity(CoordinatorEntity[MelCloudDeviceUpdateCoordinator]):
    """Base class for MELCloud entities."""

    _attr_has_entity_name = True

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.device_available


class MelCloudDescriptionEntity(MelCloudEntity):
    """Base class for description-driven MELCloud device entities."""

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{coordinator.device.mac}-{description.key}"
        )
        self._attr_device_info = coordinator.device_info


class AtwZoneEntity(MelCloudEntity):
    """Base class for Air-to-Water zone entities."""

    def __init__(
        self, coordinator: MelCloudDeviceUpdateCoordinator, zone: Zone
    ) -> None:
        """Initialize the zone entity."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_device_info = coordinator.zone_device_info(zone)
