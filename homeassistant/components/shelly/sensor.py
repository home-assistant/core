"""Sensor for Shelly."""
from homeassistant.components import sensor
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)

from .entity import (
    BlockAttributeDescription,
    ShellyBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    temperature_unit,
)

SENSORS = {
    ("device", "battery"): BlockAttributeDescription(
        name="Battery", unit=PERCENTAGE, device_class=sensor.DEVICE_CLASS_BATTERY
    ),
    ("device", "deviceTemp"): BlockAttributeDescription(
        name="Device Temperature",
        unit=temperature_unit,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_TEMPERATURE,
        default_enabled=False,
    ),
    ("emeter", "current"): BlockAttributeDescription(
        name="Current",
        unit=ELECTRICAL_CURRENT_AMPERE,
        value=lambda value: value,
        device_class=sensor.DEVICE_CLASS_CURRENT,
    ),
    ("light", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        default_enabled=False,
    ),
    ("device", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
    ),
    ("emeter", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
    ),
    ("relay", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
    ),
    ("device", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
    ),
    ("emeter", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
    ),
    ("light", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        default_enabled=False,
    ),
    ("relay", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
    ),
    ("sensor", "concentration"): BlockAttributeDescription(
        name="Gas Concentration",
        unit=CONCENTRATION_PARTS_PER_MILLION,
        value=lambda value: value,
        # "sensorOp" is "normal" when the Shelly Gas is working properly and taking measurements.
        available=lambda block: block.sensorOp == "normal",
    ),
    ("sensor", "extTemp"): BlockAttributeDescription(
        name="Temperature",
        unit=temperature_unit,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_TEMPERATURE,
    ),
    ("sensor", "humidity"): BlockAttributeDescription(
        name="Humidity",
        unit=PERCENTAGE,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_HUMIDITY,
    ),
    ("sensor", "luminosity"): BlockAttributeDescription(
        name="Luminosity",
        unit="lx",
        device_class=sensor.DEVICE_CLASS_ILLUMINANCE,
    ),
    ("sensor", "tilt"): BlockAttributeDescription(name="tilt", unit=DEGREE),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    await async_setup_entry_attribute_entities(
        hass, config_entry, async_add_entities, SENSORS, ShellySensor
    )


class ShellySensor(ShellyBlockAttributeEntity):
    """Represent a shelly sensor."""

    @property
    def state(self):
        """Return value of sensor."""
        return self.attribute_value
