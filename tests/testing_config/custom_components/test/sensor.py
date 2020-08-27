"""
Provide a mock sensor platform.

Call init before using it in your tests to ensure clean test data.
"""
import homeassistant.components.sensor as sensor
from homeassistant.const import UNIT_PERCENTAGE

from tests.common import MockEntity

DEVICE_CLASSES = list(sensor.DEVICE_CLASSES)
DEVICE_CLASSES.append("none")

UNITS_OF_MEASUREMENT = {
    sensor.DEVICE_CLASS_BATTERY: UNIT_PERCENTAGE,  # % of battery that is left
    sensor.DEVICE_CLASS_HUMIDITY: UNIT_PERCENTAGE,  # % of humidity in the air
    sensor.DEVICE_CLASS_ILLUMINANCE: "lm",  # current light level (lx/lm)
    sensor.DEVICE_CLASS_SIGNAL_STRENGTH: "dB",  # signal strength (dB/dBm)
    sensor.DEVICE_CLASS_TEMPERATURE: "C",  # temperature (C/F)
    sensor.DEVICE_CLASS_TIMESTAMP: "hh:mm:ss",  # timestamp (ISO8601)
    sensor.DEVICE_CLASS_PRESSURE: "hPa",  # pressure (hPa/mbar)
    sensor.DEVICE_CLASS_POWER: "kW",  # power (W/kW)
    sensor.DEVICE_CLASS_CURRENT: "A",  # current (A)
    sensor.DEVICE_CLASS_ENERGY: "kWh",  # energy (Wh/kWh)
    sensor.DEVICE_CLASS_POWER_FACTOR: "%",  # power factor (no unit, min: -1.0, max: 1.0)
    sensor.DEVICE_CLASS_VOLTAGE: "V",  # voltage (V)
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


class MockSensor(MockEntity):
    """Mock Sensor class."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._handle("device_class")

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of this sensor."""
        return self._handle("unit_of_measurement")
