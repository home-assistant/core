"""Base entity for weatherkit."""

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WeatherKitDataUpdateCoordinator


class WeatherKitEntity(Entity):
    """Base entity for all WeatherKit platforms."""

    def __init__(self, coordinator: WeatherKitDataUpdateCoordinator) -> None:
        """Initialize the entity with device info and unique ID."""
        config_data = coordinator.config_entry.data
        self._attr_unique_id = (
            f"{config_data[CONF_LATITUDE]}-{config_data[CONF_LONGITUDE]}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=MANUFACTURER,
        )
