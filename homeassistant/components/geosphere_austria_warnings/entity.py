"""Base entity for the GeoSphere Austria Warnings integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, WARNINGS_URL
from .coordinator import GeoSphereUpdateCoordinator


class GeoSphereEntity(CoordinatorEntity[GeoSphereUpdateCoordinator]):
    """Common base entity for all GeoSphere Austria Warnings entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeoSphereUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        municipality = coordinator.data.municipality
        self._attr_unique_id = f"{municipality.municipality_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, municipality.municipality_id)},
            name=municipality.name,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=WARNINGS_URL,
        )
