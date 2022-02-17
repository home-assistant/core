"""Entity for the SleepIQ integration."""
from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ICON_OCCUPIED, SENSOR_TYPES


class SleepIQSensor(CoordinatorEntity):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        name: str,
    ) -> None:
        """Initialize the SleepIQ side entity."""
        super().__init__(coordinator)
        self.bed = bed
        self.sleeper = sleeper

        self._attr_name = (
            f"SleepNumber {self.bed.name} {self.sleeper.name} {SENSOR_TYPES[name]}"
        )
        self._attr_unique_id = f"{self.bed.id}_{self.sleeper.name}_{name}"
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_attrs)
        )
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
