"""Sensor platform for the ezbeq Profile Loader integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EzBEQConfigEntry
from .coordinator import EzbeqCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzBEQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ezbeq sensors based on a config entry."""
    coordinator: EzbeqCoordinator = entry.runtime_data

    sensors = [
        EzbeqCurrentProfileSensor(coordinator),
    ]

    async_add_entities(sensors)


class EzbeqCurrentProfileSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the currently loaded ezbeq profile."""

    coordinator: EzbeqCoordinator

    def __init__(self, coordinator: EzbeqCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "ezbeq Current Profile"
        self._attr_unique_id = f"{coordinator.client.server_url}_current_profile"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.current_profile
