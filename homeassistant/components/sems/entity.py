"""Base class for SEMS sensors."""

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SemsDataUpdateCoordinator


class BaseSemsSensor(CoordinatorEntity, SensorEntity):
    """Base class for Sems Sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        model: str,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        coordinator: SemsDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)

        self.deviceName = name
        self.deviceModel = model
        self.coordinator = coordinator
        self._config_entry_id = config_entry.entry_id
        self.entity_description = description
        self._attr_unique_id = f"{name}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            manufacturer="Goodwe",
            model=model,
            name=name,
        )
