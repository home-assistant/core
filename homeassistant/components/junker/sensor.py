"""Sensor platform for Junker."""

from datetime import timedelta
from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_WASTE_TYPES
from .coordinator import JunkerConfigEntry, JunkerDataUpdateCoordinator
from .entity import JunkerEntity

PARALLEL_UPDATES = 0

_ATTR_WASTE_TYPES = "waste_types"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JunkerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Junker sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            JunkerTomorrowSensor(coordinator, entry),
            *(
                JunkerDaysSensor(coordinator, entry, waste_type, name)
                for waste_type, name in entry.options.get(CONF_WASTE_TYPES, {}).items()
            ),
        ]
    )


class JunkerDaysSensor(JunkerEntity, SensorEntity):
    """Days until the next collection of a waste type."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(
        self,
        coordinator: JunkerDataUpdateCoordinator,
        entry: JunkerConfigEntry,
        waste_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._waste_type = waste_type
        self._attr_name = name
        self._attr_unique_id = f"{self._identifier}_{waste_type.casefold()}"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the days until the next collection, today excluded."""
        today = dt_util.now().date()
        return next(
            (
                (collection.date - today).days
                for collection in self.coordinator.data
                if collection.waste_type == self._waste_type and collection.date > today
            ),
            None,
        )


class JunkerTomorrowSensor(JunkerEntity, SensorEntity):
    """What to throw out tomorrow."""

    _attr_translation_key = "tomorrow_collection"

    def __init__(
        self,
        coordinator: JunkerDataUpdateCoordinator,
        entry: JunkerConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._identifier}_tomorrow_collection"

    def _tomorrow(self) -> list[str]:
        day = dt_util.now().date() + timedelta(days=1)
        return [c.waste_type for c in self.collections if c.date == day]

    @property
    @override
    def available(self) -> bool:
        """Unavailable when nothing is collected tomorrow."""
        return super().available and bool(self._tomorrow())

    @property
    @override
    def native_value(self) -> str:
        """Return the waste types collected tomorrow."""
        return ", ".join(self._tomorrow())

    @property
    @override
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """Return the waste types collected tomorrow."""
        return {_ATTR_WASTE_TYPES: self._tomorrow()}
