"""Sensor platform for the Papouch integration."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator


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
        entities.append(PapouchTemperatureSensor(coordinator, entry, item_id))

    for item_id in coordinator.data.get("din_cnt", {}):
        entities.append(PapouchCounterSensor(coordinator, entry, item_id))

    async_add_entities(entities)


class PapouchTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a temperature sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        item_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_temp_{item_id}"
        self._attr_name = f"Temperature {item_id}"

        self._attr_device_info = {
            "identifiers": {(entry.domain, entry.entry_id)},
            "name": "Papouch Quido",
            "manufacturer": "Papouch s.r.o.",
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("temp", {}).get(self.item_id)


class PapouchCounterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a pulse counter."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = None
    _attr_native_unit_of_measurement = "pulses"

    def __init__(self, coordinator, entry, item_id) -> None:
        super().__init__(coordinator)
        self.item_id = item_id
        self._attr_unique_id = f"{entry.entry_id}_din_cnt_{item_id}"
        self._attr_name = f"Input {item_id} Count"
        self._attr_device_info = {
            "identifiers": {(entry.domain, entry.entry_id)},
            "name": "Papouch Quido",
            "manufacturer": "Papouch s.r.o.",
        }

    @property
    def native_value(self) -> int:
        """Return the pulse count."""
        return self.coordinator.data.get("din_cnt", {}).get(self.item_id, 0)
