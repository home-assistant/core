"""Support for Aseko Pool Live sensors."""
from __future__ import annotations

from aioaseko import Unit, Variable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator
from .entity import AsekoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aseko Pool Live sensors."""
    data: list[tuple[Unit, AsekoDataUpdateCoordinator]] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = []
    for unit, coordinator in data:
        for variable in unit.variables:
            entities.append(VariableSensorEntity(unit, variable, coordinator))
    async_add_entities(entities)


class VariableSensorEntity(AsekoEntity, SensorEntity):
    """Representation of a unit variable sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, unit: Unit, variable: Variable, coordinator: AsekoDataUpdateCoordinator
    ) -> None:
        """Initialize the variable sensor."""
        super().__init__(unit, coordinator)
        self._variable = variable

        translation_key = {
            "Air temp.": "air_temperature",
            "Cl free": "free_chlorine",
            "Water temp.": "water_temperature",
        }.get(self._variable.name)
        if translation_key is not None:
            self._attr_translation_key = translation_key
        else:
            self._attr_name = self._variable.name

        self._attr_unique_id = f"{self._unit.serial_number}{self._variable.type}"
        self._attr_native_unit_of_measurement = self._variable.unit

        self._attr_icon = {
            "rx": "mdi:test-tube",
            "waterLevel": "mdi:waves",
        }.get(self._variable.type)

        self._attr_device_class = {
            "airTemp": SensorDeviceClass.TEMPERATURE,
            "waterTemp": SensorDeviceClass.TEMPERATURE,
            "ph": SensorDeviceClass.PH,
        }.get(self._variable.type)

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        variable = self.coordinator.data[self._variable.type]
        return variable.current_value
