"""Base entity for weatherkit."""

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WeatherKitDataUpdateCoordinator


class WeatherKitEntity(Entity):
    """Base entity for all WeatherKit platforms."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WeatherKitDataUpdateCoordinator, unique_id_suffix: str | None
    ) -> None:
        """Initialize the entity with device info and unique ID."""
        config_data = coordinator.config_entry.data

        config_entry_unique_id = (
            f"{config_data[CONF_LATITUDE]}-{config_data[CONF_LONGITUDE]}"
        )
        self._attr_unique_id = config_entry_unique_id
        if unique_id_suffix is not None:
            self._attr_unique_id += f"_{unique_id_suffix}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry_unique_id)},
            manufacturer=MANUFACTURER,
        )
