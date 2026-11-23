"""The base entity of the Osmund integration: one device per location."""

from osmund import Location

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_URL
from .coordinator import OsmundCoordinator


class OsmundEntity(CoordinatorEntity[OsmundCoordinator]):
    """An entity of one location, keyed on the API's location id, never on a name."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OsmundCoordinator, location: Location, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.location_id = location.id
        self._attr_unique_id = f"{location.id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location.id)},
            name=location.label or "Osmund",
            manufacturer="Osmund",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=KEY_URL,
        )
