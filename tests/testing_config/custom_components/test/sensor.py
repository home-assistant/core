"""
Provide a mock sensor platform.

Call init before using it in your tests to ensure clean test data.
"""
import homeassistant.components.sensor as sensor
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    FREQUENCY_GIGAHERTZ,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS,
    VOLUME_CUBIC_METERS,
)

from tests.common import MockEntity

DEVICE_CLASSES = list(sensor.DEVICE_CLASSES)
DEVICE_CLASSES.append("none")

UNITS_OF_MEASUREMENT = {
    sensor.DEVICE_CLASS_BATTERY: PERCENTAGE,  # % of battery that is left
    sensor.DEVICE_CLASS_CO: CONCENTRATION_PARTS_PER_MILLION,  # ppm of CO concentration
    sensor.DEVICE_CLASS_CO2: CONCENTRATION_PARTS_PER_MILLION,  # ppm of CO2 concentration
    sensor.DEVICE_CLASS_HUMIDITY: PERCENTAGE,  # % of humidity in the air
    sensor.DEVICE_CLASS_ILLUMINANCE: "lm",  # current light level (lx/lm)
    sensor.DEVICE_CLASS_NITROGEN_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen dioxide
    sensor.DEVICE_CLASS_NITROGEN_MONOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen monoxide
    sensor.DEVICE_CLASS_NITROUS_OXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen oxide
    sensor.DEVICE_CLASS_OZONE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of ozone
    sensor.DEVICE_CLASS_PM1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM1
    sensor.DEVICE_CLASS_PM10: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM10
    sensor.DEVICE_CLASS_PM25: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM2.5
    sensor.DEVICE_CLASS_SIGNAL_STRENGTH: SIGNAL_STRENGTH_DECIBELS,  # signal strength (dB/dBm)
    sensor.DEVICE_CLASS_SULPHUR_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of sulphur dioxide
    sensor.DEVICE_CLASS_TEMPERATURE: "C",  # temperature (C/F)
    sensor.DEVICE_CLASS_PRESSURE: PRESSURE_HPA,  # pressure (hPa/mbar)
    sensor.DEVICE_CLASS_POWER: "kW",  # power (W/kW)
    sensor.DEVICE_CLASS_CURRENT: "A",  # current (A)
    sensor.DEVICE_CLASS_ENERGY: "kWh",  # energy (Wh/kWh)
    sensor.DEVICE_CLASS_FREQUENCY: FREQUENCY_GIGAHERTZ,  # energy (Hz/kHz/MHz/GHz)
    sensor.DEVICE_CLASS_POWER_FACTOR: PERCENTAGE,  # power factor (no unit, min: -1.0, max: 1.0)
    sensor.DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of vocs
    sensor.DEVICE_CLASS_VOLTAGE: "V",  # voltage (V)
    sensor.DEVICE_CLASS_GAS: VOLUME_CUBIC_METERS,  # gas (m³)
}

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            device_class: MockSensor(
                name=f"{device_class} sensor",
                unique_id=f"unique_{device_class}",
                device_class=device_class,
                unit_of_measurement=UNITS_OF_MEASUREMENT.get(device_class),
            )
            for device_class in DEVICE_CLASSES
        }
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockSensor(MockEntity, sensor.SensorEntity):
    """Mock Sensor class."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._handle("device_class")

    @property
    def last_reset(self):
        """Return the last_reset of this sensor."""
        return self._handle("last_reset")

    @property
    def native_unit_of_measurement(self):
        """Return the native unit_of_measurement of this sensor."""
        return self._handle("native_unit_of_measurement")

    @property
    def native_value(self):
        """Return the native value of this sensor."""
        return self._handle("native_value")

    @property
    def state_class(self):
        """Return the state class of this sensor."""
        return self._handle("state_class")
