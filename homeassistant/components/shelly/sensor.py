"""Sensor for Shelly."""
from homeassistant.components import sensor
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    VOLT,
)

from .const import SHAIR_MAX_WORK_HOURS
from .entity import (
    BlockAttributeDescription,
    RestAttributeDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
)
from .utils import get_device_uptime, temperature_unit

SENSORS = {
    ("device", "battery"): BlockAttributeDescription(
        name="Battery",
        unit=PERCENTAGE,
        device_class=sensor.DEVICE_CLASS_BATTERY,
        removal_condition=lambda settings, _: settings.get("external_power") == 1,
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
    ("emeter", "voltage"): BlockAttributeDescription(
        name="Voltage",
        unit=VOLT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
    ),
    ("emeter", "powerFactor"): BlockAttributeDescription(
        name="Power Factor",
        unit=PERCENTAGE,
        value=lambda value: round(value * 100, 1),
        device_class=sensor.DEVICE_CLASS_POWER_FACTOR,
    ),
    ("relay", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
    ),
    ("roller", "rollerPower"): BlockAttributeDescription(
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
    ("emeter", "energyReturned"): BlockAttributeDescription(
        name="Energy Returned",
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
    ("roller", "rollerEnergy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
    ),
    ("sensor", "concentration"): BlockAttributeDescription(
        name="Gas Concentration",
        unit=CONCENTRATION_PARTS_PER_MILLION,
        value=lambda value: value,
        icon="mdi:gauge",
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
        unit=LIGHT_LUX,
        device_class=sensor.DEVICE_CLASS_ILLUMINANCE,
    ),
    ("sensor", "tilt"): BlockAttributeDescription(name="Tilt", unit=DEGREE),
    ("relay", "totalWorkTime"): BlockAttributeDescription(
        name="Lamp life",
        unit=PERCENTAGE,
        icon="mdi:progress-wrench",
        value=lambda value: round(100 - (value / 3600 / SHAIR_MAX_WORK_HOURS), 1),
        device_state_attributes=lambda block: {
            "Operational hours": round(block.totalWorkTime / 3600, 1)
        },
    ),
    ("adc", "adc"): BlockAttributeDescription(
        name="ADC",
        unit=VOLT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
    ),
}

REST_SENSORS = {
    "rssi": RestAttributeDescription(
        name="RSSI",
        unit=SIGNAL_STRENGTH_DECIBELS,
        value=lambda status, _: status["wifi_sta"]["rssi"],
        device_class=sensor.DEVICE_CLASS_SIGNAL_STRENGTH,
        default_enabled=False,
    ),
    "uptime": RestAttributeDescription(
        name="Uptime",
        value=get_device_uptime,
        device_class=sensor.DEVICE_CLASS_TIMESTAMP,
        default_enabled=False,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    if config_entry.data["sleep_period"]:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, SENSORS, ShellySleepingSensor
        )
    else:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, SENSORS, ShellySensor
        )
        await async_setup_entry_rest(
            hass, config_entry, async_add_entities, REST_SENSORS, ShellyRestSensor
        )


class ShellySensor(ShellyBlockAttributeEntity):
    """Represent a shelly sensor."""

    @property
    def state(self):
        """Return value of sensor."""
        return self.attribute_value


class ShellyRestSensor(ShellyRestAttributeEntity):
    """Represent a shelly REST sensor."""

    @property
    def state(self):
        """Return value of sensor."""
        return self.attribute_value


class ShellySleepingSensor(ShellySleepingBlockAttributeEntity):
    """Represent a shelly sleeping sensor."""

    @property
    def state(self):
        """Return value of sensor."""
        if self.block is not None:
            return self.attribute_value

        return self.last_state
