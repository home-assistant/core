"""Shared location device and entity identity."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XiaomiWeatherConfigEntry, XiaomiWeatherCoordinator


class XiaomiWeatherEntity(CoordinatorEntity[XiaomiWeatherCoordinator]):
    """An entity backed by the location's shared coordinator."""

    _attr_has_entity_name = True

    def __init__(self, entry: XiaomiWeatherConfigEntry, key: str) -> None:
        """Set stable identity and a service device."""
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name=entry.title,
            manufacturer="Xiaomi",
            entry_type=DeviceEntryType.SERVICE,
        )
