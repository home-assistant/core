"""Support for Aseko Pool Live sensors."""

from __future__ import annotations

from aioaseko import Unit, Variable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator
from .entity import AsekoEntity

CONCENTRATION_KILOGRAMS_PER_CUBIC_METER = "kg/m³"
CONCENTRATION_MILLIGRAMS_PER_LITER = "mg/l"
GRAMS_PER_HOUR = "g/hour"

UNIT_SENSORS = {
    "airTemp": SensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "waterTemp": SensorEntityDescription(
        key="water_temperature",
        translation_key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "ph": SensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
    ),
    "rx": SensorEntityDescription(
        key="redox",
        translation_key="redox",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        icon="mdi:test-tube",
    ),
    "electrodePower": SensorEntityDescription(
        key="electrolyzer",
        translation_key="electrolyzer",
        native_unit_of_measurement=GRAMS_PER_HOUR,
        icon="mdi:lightning-bolt",
    ),
    "clf": SensorEntityDescription(
        key="free_chlorine",
        translation_key="free_chlorine",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_LITER,
        icon="mdi:test-tube",
    ),
    "salinity": SensorEntityDescription(
        key="salinity",
        translation_key="salinity",
        native_unit_of_measurement=CONCENTRATION_KILOGRAMS_PER_CUBIC_METER,
    ),
    "waterLevel": SensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        icon="mdi:waves",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aseko Pool Live sensors."""
    data: list[tuple[Unit, AsekoDataUpdateCoordinator]] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        VariableSensorEntity(unit, variable, coordinator)
        for unit, coordinator in data
        for variable in unit.variables
    )


class VariableSensorEntity(AsekoEntity, SensorEntity):
    """Representation of a unit variable sensor entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, unit: Unit, variable: Variable, coordinator: AsekoDataUpdateCoordinator
    ) -> None:
        """Initialize the variable sensor."""
        super().__init__(unit, coordinator)
        self._variable = variable

        entity_description = UNIT_SENSORS.get(self._variable.type)
        if entity_description is not None:
            self.entity_description = entity_description
        else:
            self._attr_name = self._variable.name
            self._attr_native_unit_of_measurement = self._variable.unit

        self._attr_unique_id = f"{self._unit.serial_number}{self._variable.type}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        variable = self.coordinator.data[self._variable.type]
        return variable.current_value
