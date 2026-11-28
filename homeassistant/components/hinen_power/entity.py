"""Entity representing a Hinen Power."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DEVICE_NAME, ATTR_SERIAL_NUMBER, DOMAIN, MANUFACTURER
from .coordinator import HinenDataUpdateCoordinator


class HinenDeviceEntity(CoordinatorEntity[HinenDataUpdateCoordinator]):
    """An HA implementation for Hinen entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HinenDataUpdateCoordinator,
        description: EntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a Hinen entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{device_id}_{description.key}"
        )
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.config_entry.unique_id}_{device_id}")},
            manufacturer=MANUFACTURER,
            name=coordinator.data.get(device_id, {}).get(ATTR_DEVICE_NAME),
            serial_number=coordinator.data.get(device_id, {}).get(ATTR_SERIAL_NUMBER),
        )
