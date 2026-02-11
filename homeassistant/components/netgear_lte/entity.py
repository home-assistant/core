"""Entity representing a Netgear LTE entity."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NetgearLTEConfigEntry, NetgearLTEDataUpdateCoordinator


class LTEEntity(CoordinatorEntity[NetgearLTEDataUpdateCoordinator]):
    """Base LTE entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: NetgearLTEConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize a Netgear LTE entity."""
        super().__init__(entry.runtime_data)
        self.entity_description = description
        data = entry.runtime_data.data
        self._attr_unique_id = f"{description.key}_{data.serial_number}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, data.serial_number)},
            manufacturer=MANUFACTURER,
            model=data.items["general.model"],
            serial_number=data.serial_number,
            sw_version=data.items["general.fwversion"],
            hw_version=data.items["general.hwversion"],
        )
