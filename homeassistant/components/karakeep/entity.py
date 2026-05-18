"""Base entity for the Karakeep integration."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KarakeepDataUpdateCoordinator


class KarakeepEntity(CoordinatorEntity[KarakeepDataUpdateCoordinator]):
    """Base class for Karakeep entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KarakeepDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {
                (DOMAIN, coordinator.config_entry.data[CONF_URL]),
            },
            "name": "Karakeep",
            "manufacturer": "Karakeep",
            "entry_type": DeviceEntryType.SERVICE,
        }
