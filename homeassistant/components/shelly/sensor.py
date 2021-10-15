"""Sensor for Shelly."""
from __future__ import annotations

from typing import Final, cast

from homeassistant.components import sensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import SHAIR_MAX_WORK_HOURS
from .entity import (
    BlockAttributeDescription,
    RestAttributeDescription,
    RpcAttributeDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen, get_device_uptime, temperature_unit

SENSORS: Final = {
    ("device", "battery"): BlockAttributeDescription(
        name="Battery",
        unit=PERCENTAGE,
        device_class=sensor.DEVICE_CLASS_BATTERY,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        removal_condition=lambda settings, _: settings.get("external_power") == 1,
        available=lambda block: cast(int, block.battery) != -1,
    ),
    ("device", "deviceTemp"): BlockAttributeDescription(
        name="Device Temperature",
        unit=temperature_unit,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_TEMPERATURE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    ("emeter", "current"): BlockAttributeDescription(
        name="Current",
        unit=ELECTRIC_CURRENT_AMPERE,
        value=lambda value: value,
        device_class=sensor.DEVICE_CLASS_CURRENT,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("light", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    ("device", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("emeter", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("device", "voltage"): BlockAttributeDescription(
        name="Voltage",
        unit=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    ("emeter", "voltage"): BlockAttributeDescription(
        name="Voltage",
        unit=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("emeter", "powerFactor"): BlockAttributeDescription(
        name="Power Factor",
        unit=PERCENTAGE,
        value=lambda value: round(value * 100, 1),
        device_class=sensor.DEVICE_CLASS_POWER_FACTOR,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("relay", "power"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("roller", "rollerPower"): BlockAttributeDescription(
        name="Power",
        unit=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("device", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    ("emeter", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    ("emeter", "energyReturned"): BlockAttributeDescription(
        name="Energy Returned",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    ("light", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
        default_enabled=False,
    ),
    ("relay", "energy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    ("roller", "rollerEnergy"): BlockAttributeDescription(
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    ("sensor", "concentration"): BlockAttributeDescription(
        name="Gas Concentration",
        unit=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:gauge",
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("sensor", "extTemp"): BlockAttributeDescription(
        name="Temperature",
        unit=temperature_unit,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_TEMPERATURE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        available=lambda block: cast(int, block.extTemp) != 999,
    ),
    ("sensor", "humidity"): BlockAttributeDescription(
        name="Humidity",
        unit=PERCENTAGE,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_HUMIDITY,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        available=lambda block: cast(int, block.humidity) != 999,
    ),
    ("sensor", "luminosity"): BlockAttributeDescription(
        name="Luminosity",
        unit=LIGHT_LUX,
        device_class=sensor.DEVICE_CLASS_ILLUMINANCE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        available=lambda block: cast(int, block.luminosity) != -1,
    ),
    ("sensor", "tilt"): BlockAttributeDescription(
        name="Tilt",
        unit=DEGREE,
        icon="mdi:angle-acute",
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("relay", "totalWorkTime"): BlockAttributeDescription(
        name="Lamp Life",
        unit=PERCENTAGE,
        icon="mdi:progress-wrench",
        value=lambda value: round(100 - (value / 3600 / SHAIR_MAX_WORK_HOURS), 1),
        extra_state_attributes=lambda block: {
            "Operational hours": round(cast(int, block.totalWorkTime) / 3600, 1)
        },
    ),
    ("adc", "adc"): BlockAttributeDescription(
        name="ADC",
        unit=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    ("sensor", "sensorOp"): BlockAttributeDescription(
        name="Operation",
        icon="mdi:cog-transfer",
        value=lambda value: value,
        extra_state_attributes=lambda block: {"self_test": block.selfTest},
    ),
}

REST_SENSORS: Final = {
    "rssi": RestAttributeDescription(
        name="RSSI",
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value=lambda status, _: status["wifi_sta"]["rssi"],
        device_class=sensor.DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    "uptime": RestAttributeDescription(
        name="Uptime",
        value=lambda status, last: get_device_uptime(status["uptime"], last),
        device_class=sensor.DEVICE_CLASS_TIMESTAMP,
        default_enabled=False,
    ),
}


RPC_SENSORS: Final = {
    "power": RpcAttributeDescription(
        key="switch",
        sub_key="apower",
        name="Power",
        unit=POWER_WATT,
        value=lambda status, _: round(float(status), 1),
        device_class=sensor.DEVICE_CLASS_POWER,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
    ),
    "voltage": RpcAttributeDescription(
        key="switch",
        sub_key="voltage",
        name="Voltage",
        unit=ELECTRIC_POTENTIAL_VOLT,
        value=lambda status, _: round(float(status), 1),
        device_class=sensor.DEVICE_CLASS_VOLTAGE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    "energy": RpcAttributeDescription(
        key="switch",
        sub_key="aenergy",
        name="Energy",
        unit=ENERGY_KILO_WATT_HOUR,
        value=lambda status, _: round(status["total"] / 1000, 2),
        device_class=sensor.DEVICE_CLASS_ENERGY,
        state_class=sensor.STATE_CLASS_TOTAL_INCREASING,
    ),
    "temperature": RpcAttributeDescription(
        key="switch",
        sub_key="temperature",
        name="Temperature",
        unit=TEMP_CELSIUS,
        value=lambda status, _: round(status["tC"], 1),
        device_class=sensor.DEVICE_CLASS_TEMPERATURE,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    "rssi": RpcAttributeDescription(
        key="wifi",
        sub_key="rssi",
        name="RSSI",
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=sensor.DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=sensor.STATE_CLASS_MEASUREMENT,
        default_enabled=False,
    ),
    "uptime": RpcAttributeDescription(
        key="sys",
        sub_key="uptime",
        name="Uptime",
        value=get_device_uptime,
        device_class=sensor.DEVICE_CLASS_TIMESTAMP,
        default_enabled=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) == 2:
        return await async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_SENSORS, RpcSensor
        )

    if config_entry.data["sleep_period"]:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, SENSORS, BlockSleepingSensor
        )
    else:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, SENSORS, BlockSensor
        )
        await async_setup_entry_rest(
            hass, config_entry, async_add_entities, REST_SENSORS, RestSensor
        )


class BlockSensor(ShellyBlockAttributeEntity, SensorEntity):
    """Represent a block sensor."""

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value

    @property
    def state_class(self) -> str | None:
        """State class of sensor."""
        return self.description.state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of sensor."""
        return cast(str, self._unit)


class RestSensor(ShellyRestAttributeEntity, SensorEntity):
    """Represent a REST sensor."""

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value

    @property
    def state_class(self) -> str | None:
        """State class of sensor."""
        return self.description.state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of sensor."""
        return self.description.unit


class RpcSensor(ShellyRpcAttributeEntity, SensorEntity):
    """Represent a RPC sensor."""

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value

    @property
    def state_class(self) -> str | None:
        """State class of sensor."""
        return self.description.state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of sensor."""
        return self.description.unit


class BlockSleepingSensor(ShellySleepingBlockAttributeEntity, SensorEntity):
    """Represent a block sleeping sensor."""

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.block is not None:
            return self.attribute_value

        return self.last_state

    @property
    def state_class(self) -> str | None:
        """State class of sensor."""
        return self.description.state_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of sensor."""
        return cast(str, self._unit)
