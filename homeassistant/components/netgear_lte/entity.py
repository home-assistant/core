"""Entity representing a Netgear LTE entity."""
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NetgearLTEDataUpdateCoordinator


class LTEEntity(CoordinatorEntity[NetgearLTEDataUpdateCoordinator]):
    """Base LTE entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetgearLTEDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a Netgear LTE entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}_{coordinator.data.serial_number}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer=MANUFACTURER,
            model=coordinator.data.items["general.model"],
            serial_number=coordinator.data.serial_number,
            sw_version=coordinator.data.items["general.fwversion"],
            hw_version=coordinator.data.items["general.hwversion"],
        )
