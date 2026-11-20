"""Support for Nightscout sensors."""

from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import ATTR_DATE, UnitOfBloodGlucoseConcentration
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DELTA, ATTR_DEVICE, ATTR_DIRECTION
from .coordinator import NightscoutConfigEntry, NightscoutGlucoseCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

DEFAULT_NAME = "Blood Glucose"

TREND_ICONS = {
    "Flat": "mdi:arrow-right",
    "SingleDown": "mdi:arrow-down",
    "FortyFiveDown": "mdi:arrow-bottom-right",
    "DoubleDown": "mdi:chevron-triple-down",
    "SingleUp": "mdi:arrow-up",
    "FortyFiveUp": "mdi:arrow-top-right",
    "DoubleUp": "mdi:chevron-triple-up",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NightscoutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Glucose Sensor."""
    coordinator = entry.runtime_data
    async_add_entities([NightscoutSensor(coordinator, "Blood Sugar", entry.unique_id)])


class NightscoutSensor(CoordinatorEntity[NightscoutGlucoseCoordinator], SensorEntity):
    """Implementation of a Nightscout sensor."""

    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = (
        UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER
    )

    def __init__(
        self,
        coordinator: NightscoutGlucoseCoordinator,
        name: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the Nightscout sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name

    @property
    @override
    def available(self) -> bool:
        """Return if a glucose reading is available."""
        return super().available and self.coordinator.data is not None

    @property
    @override
    def native_value(self) -> int | None:
        """Return the latest glucose value."""
        reading = self.coordinator.data
        return int(reading.sgv) if reading else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the latest glucose reading."""
        reading = self.coordinator.data
        return (
            {
                ATTR_DEVICE: reading.device,
                ATTR_DATE: reading.date,
                ATTR_DELTA: reading.delta,
                ATTR_DIRECTION: reading.direction,
            }
            if reading
            else None
        )

    @property
    @override
    def icon(self) -> str:
        """Return an icon matching the trend direction."""
        reading = self.coordinator.data
        if reading is None:
            return "mdi:cloud-question"
        return TREND_ICONS.get(reading.direction, "mdi:cloud-question")
