"""Base entity for weatherkit."""

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
        entry_id = coordinator.config_entry.entry_id

        self._attr_unique_id = entry_id
        if unique_id_suffix is not None:
            self._attr_unique_id += f"_{unique_id_suffix}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
        )
