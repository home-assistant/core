"""Base entity for the Helty Flow integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeltyDataUpdateCoordinator


class HeltyEntity(CoordinatorEntity[HeltyDataUpdateCoordinator]):
    """Common base for Helty entities sharing one device and coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeltyDataUpdateCoordinator) -> None:
        """Initialize the entity and its shared device info."""
        super().__init__(coordinator)
        # The unit exposes no serial/MAC, so the config entry id identifies it.
        self._device_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=coordinator.data.name,
            manufacturer="Helty",
            model="Flow",
        )
