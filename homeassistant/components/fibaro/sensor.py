"""Support for Fibaro sensors."""
from __future__ import annotations

from contextlib import suppress

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

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        if fibaro_device.type in SENSOR_TYPES:
            self._unit = SENSOR_TYPES[fibaro_device.type][1]
            self._icon = SENSOR_TYPES[fibaro_device.type][2]
            self._device_class = SENSOR_TYPES[fibaro_device.type][3]
            self._attr_state_class = SENSOR_TYPES[fibaro_device.type][4]
        else:
            self._unit = None
            self._icon = None
            self._device_class = None
        with suppress(KeyError, ValueError):
            if not self._unit:
                if self.fibaro_device.properties.unit == "lux":
                    self._unit = LIGHT_LUX
                elif self.fibaro_device.properties.unit == "C":
                    self._unit = TEMP_CELSIUS
                elif self.fibaro_device.properties.unit == "F":
                    self._unit = TEMP_FAHRENHEIT
                else:
                    self._unit = self.fibaro_device.properties.unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    def update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            self.current_value = float(self.fibaro_device.properties.value)


class FibaroEnergySensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.ha_id}_energy")
        self._attr_name = f"{fibaro_device.friendly_name} Energy"
        self._attr_unique_id = f"{fibaro_device.unique_id_str}_energy"

    def update(self):
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

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.ha_id}_power")
        self._attr_name = f"{fibaro_device.friendly_name} Power"
        self._attr_unique_id = f"{fibaro_device.unique_id_str}_power"

    def update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            self._attr_native_value = convert(
                self.fibaro_device.properties.power, float
            )
