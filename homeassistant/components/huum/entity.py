"""Define Huum Base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator


class HuumBaseEntity(CoordinatorEntity[HuumDataUpdateCoordinator]):
    """Huum base Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Huum sauna",
            manufacturer="Huum",
            model="UKU WiFi",
        )
