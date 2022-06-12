"""Support for Fibaro sensors."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import convert

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN

SENSOR_TYPES = {
    "com.fibaro.temperatureSensor": [
        "Temperature",
        None,
        None,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
    ],
    "com.fibaro.smokeSensor": [
        "Smoke",
        CONCENTRATION_PARTS_PER_MILLION,
        "mdi:fire",
        None,
        None,
    ],
    "CO2": [
        "CO2",
        CONCENTRATION_PARTS_PER_MILLION,
        None,
        SensorDeviceClass.CO2,
        SensorStateClass.MEASUREMENT,
    ],
    "com.fibaro.humiditySensor": [
        "Humidity",
        PERCENTAGE,
        None,
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
    ],
    "com.fibaro.lightSensor": [
        "Light",
        LIGHT_LUX,
        None,
        SensorDeviceClass.ILLUMINANCE,
        SensorStateClass.MEASUREMENT,
    ],
    "com.fibaro.energyMeter": [
        "Energy",
        ENERGY_KILO_WATT_HOUR,
        None,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro controller devices."""
    entities: list[SensorEntity] = []
    for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][Platform.SENSOR]:
        entities.append(FibaroSensor(device))
    for platform in (Platform.COVER, Platform.LIGHT, Platform.SENSOR, Platform.SWITCH):
        for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][platform]:
            if "energy" in device.interfaces:
                entities.append(FibaroEnergySensor(device))
            if "power" in device.interfaces:
                entities.append(FibaroPowerSensor(device))

    async_add_entities(entities, True)


class FibaroSensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Sensor."""

    def __init__(self, fibaro_device: Any) -> None:
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        self._attr_native_unit_of_measurement = None
        if fibaro_device.type in SENSOR_TYPES:
            self._attr_native_unit_of_measurement = SENSOR_TYPES[fibaro_device.type][1]
            self._attr_icon = SENSOR_TYPES[fibaro_device.type][2]
            self._attr_device_class = SENSOR_TYPES[fibaro_device.type][3]
            self._attr_state_class = SENSOR_TYPES[fibaro_device.type][4]

        with suppress(KeyError, ValueError):
            if not self._attr_native_unit_of_measurement:
                unit = self.fibaro_device.properties.unit
                if unit == "lux":
                    self._attr_native_unit_of_measurement = LIGHT_LUX
                elif unit == "C":
                    self._attr_native_unit_of_measurement = TEMP_CELSIUS
                elif unit == "F":
                    self._attr_native_unit_of_measurement = TEMP_FAHRENHEIT
                else:
                    self._attr_native_unit_of_measurement = unit

    def update(self) -> None:
        """Update the state."""
        with suppress(KeyError, ValueError):
            self._attr_native_value = float(self.fibaro_device.properties.value)


class FibaroEnergySensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    def __init__(self, fibaro_device: Any) -> None:
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.ha_id}_energy")
        self._attr_name = f"{fibaro_device.friendly_name} Energy"
        self._attr_unique_id = f"{fibaro_device.unique_id_str}_energy"

    def update(self) -> None:
        """Update the state."""
        with suppress(KeyError, ValueError):
            self._attr_native_value = convert(
                self.fibaro_device.properties.energy, float
            )


class FibaroPowerSensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Power Sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_WATT

    def __init__(self, fibaro_device: Any) -> None:
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.ha_id}_power")
        self._attr_name = f"{fibaro_device.friendly_name} Power"
        self._attr_unique_id = f"{fibaro_device.unique_id_str}_power"

    def update(self) -> None:
        """Update the state."""
        with suppress(KeyError, ValueError):
            self._attr_native_value = convert(
                self.fibaro_device.properties.power, float
            )
