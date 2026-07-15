"""Sensor platform for the Papouch integration."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data

    entities = []

    # TODO: remove hard-coded names and refactor

    for item_id in coordinator.data.get("temp", {}):
        entities.append(PapouchTemperatureSensor(coordinator, entry, item_id))  # noqa: PERF401

    for item_id in coordinator.data.get("din_cnt", {}):
        entities.append(PapouchCounterSensor(coordinator, entry, item_id))  # noqa: PERF401

    async_add_entities(entities)


class PapouchTemperatureSensor(PapouchEntity, SensorEntity):
    """Representation of a temperature sensor."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        item_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_temp_{item_id}"
        self._attr_name = f"Temperature {item_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("temp", {}).get(self.item_id)


class PapouchCounterSensor(PapouchEntity, SensorEntity):
    """Representation of a pulse counter."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = None
    _attr_native_unit_of_measurement = "pulses"

    def __init__(self, coordinator, entry, item_id) -> None:
        """Constructor of the counter senzor UI."""
        super().__init__(coordinator, entry)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_din_cnt_{item_id}"
        self._attr_name = f"Input {item_id} Count"

    @property
    def native_value(self) -> int:
        """Return the pulse count."""
        return self.coordinator.data.get("din_cnt", {}).get(self.item_id, 0)
