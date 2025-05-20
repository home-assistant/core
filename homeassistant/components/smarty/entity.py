"""Smarty Entity class."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartyCoordinator


class SmartyEntity(CoordinatorEntity[SmartyCoordinator]):
    """Representation of a Smarty Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Salda",
            sw_version=self.coordinator.software_version,
            hw_version=self.coordinator.configuration_version,
        )
