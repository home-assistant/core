"""Base entity for the INDI Allsky integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndiAllSkyConfigEntry, IndiAllSkyDataUpdateCoordinator


class IndiAllSkyEntity(CoordinatorEntity[IndiAllSkyDataUpdateCoordinator]):
    """Base class for INDI Allsky entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
