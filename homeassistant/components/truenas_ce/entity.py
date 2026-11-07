"""Base entity for the TrueNAS integration."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrueNASCoordinator


class TrueNASEntity(CoordinatorEntity[TrueNASCoordinator]):
    """Base class for TrueNAS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrueNASCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        info = coordinator.data.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.system_id)},
            name=entry.title,
            manufacturer=info.manufacturer,
            model=info.product,
            serial_number=info.serial,
            sw_version=info.version,
            configuration_url=f"https://{entry.data[CONF_HOST]}",
        )
