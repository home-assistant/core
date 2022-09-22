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
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, CoilEntity, Coordinator

UNIT_DESCRIPTIONS = {
    TEMP_CELSIUS: SensorEntityDescription(
        key=TEMP_CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    TEMP_FAHRENHEIT: SensorEntityDescription(
        key=TEMP_FAHRENHEIT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_FAHRENHEIT,
    ),
    ELECTRIC_CURRENT_AMPERE: SensorEntityDescription(
        key=ELECTRIC_CURRENT_AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    ELECTRIC_CURRENT_MILLIAMPERE: SensorEntityDescription(
        key=ELECTRIC_CURRENT_MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
    ),
    ELECTRIC_POTENTIAL_VOLT: SensorEntityDescription(
        key=ELECTRIC_POTENTIAL_VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    ELECTRIC_POTENTIAL_MILLIVOLT: SensorEntityDescription(
        key=ELECTRIC_POTENTIAL_VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
    ),
    ENERGY_WATT_HOUR: SensorEntityDescription(
        key=ENERGY_WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_WATT_HOUR,
    ),
    ENERGY_KILO_WATT_HOUR: SensorEntityDescription(
        key=ENERGY_WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    ENERGY_MEGA_WATT_HOUR: SensorEntityDescription(
        key=ENERGY_MEGA_WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_MEGA_WATT_HOUR,
    ),
    TIME_HOURS: SensorEntityDescription(
        key=TIME_HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
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


class Sensor(SensorEntity, CoilEntity):
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

    def _async_read_coil(self, coil: Coil):
        self._attr_native_value = coil.value
