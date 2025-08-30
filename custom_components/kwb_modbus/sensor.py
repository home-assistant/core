"""KWB Modbus sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KwbModbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus sensor entities."""

    # Minimaler Test-Sensor
    entities = [KwbTestSensor(entry)]
    async_add_entities(entities)


class KwbTestSensor(SensorEntity):
    """Test sensor for KWB Modbus."""

    _attr_has_entity_name = True
    _attr_name = "Test sensor"

    def __init__(self, entry: KwbModbusConfigEntry) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{entry.entry_id}_test"
        self._attr_native_value = "OK"
