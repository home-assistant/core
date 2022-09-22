"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from nibe.coil import Coil

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
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
    TEMP_KELVIN,
    TIME_HOURS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, CoilEntity, Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Sensor(coordinator, coil)
        for coil in coordinator.coils
        if not coil.is_writable and not coil.is_boolean
    )


class Sensor(SensorEntity, CoilEntity):
    """Sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Coordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        self._attr_native_unit_of_measurement = coil.unit

        unit = self.native_unit_of_measurement
        if unit in {TEMP_CELSIUS, TEMP_FAHRENHEIT, TEMP_KELVIN}:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif unit in {ELECTRIC_CURRENT_AMPERE, ELECTRIC_CURRENT_MILLIAMPERE}:
            self._attr_device_class = SensorDeviceClass.CURRENT
        elif unit in {ELECTRIC_POTENTIAL_VOLT, ELECTRIC_POTENTIAL_MILLIVOLT}:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif unit in {ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR, ENERGY_MEGA_WATT_HOUR}:
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif unit in {TIME_HOURS}:
            self._attr_device_class = SensorDeviceClass.DURATION
        else:
            self._attr_device_class = None

        if unit:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _async_read_coil(self, coil: Coil):
        self._attr_native_value = coil.value
