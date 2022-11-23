"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from nibe.coil import Coil

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    ELECTRIC_POTENTIAL_VOLT,
    TIME_HOURS,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, CoilEntity, Coordinator

UNIT_DESCRIPTIONS = {
    "°C": SensorEntityDescription(
        key="°C",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "°F": SensorEntityDescription(
        key="°F",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
    "A": SensorEntityDescription(
        key="A",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    "mA": SensorEntityDescription(
        key="mA",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
    ),
    "V": SensorEntityDescription(
        key="V",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    "mV": SensorEntityDescription(
        key="mV",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
    ),
    "W": SensorEntityDescription(
        key="W",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    "kW": SensorEntityDescription(
        key="kW",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    "Wh": SensorEntityDescription(
        key="Wh",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    "kWh": SensorEntityDescription(
        key="kWh",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    "MWh": SensorEntityDescription(
        key="MWh",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
    ),
    "h": SensorEntityDescription(
        key="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=TIME_HOURS,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Sensor(coordinator, coil, UNIT_DESCRIPTIONS.get(coil.unit))
        for coil in coordinator.coils
        if not coil.is_writable and not coil.is_boolean
    )


class Sensor(CoilEntity, SensorEntity):
    """Sensor entity."""

    def __init__(
        self,
        coordinator: Coordinator,
        coil: Coil,
        entity_description: SensorEntityDescription | None,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        if entity_description:
            self.entity_description = entity_description
        else:
            self._attr_native_unit_of_measurement = coil.unit
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _async_read_coil(self, coil: Coil):
        self._attr_native_value = coil.value
