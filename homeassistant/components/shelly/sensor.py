"""Sensor for Shelly."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from aioshelly.block_device import Block

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.typing import StateType

from .const import CONF_SLEEP_PERIOD, SHAIR_MAX_WORK_HOURS
from .coordinator import ShellyBlockCoordinator
from .entity import (
    BlockEntityDescription,
    RestEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    ShellySleepingRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen, get_device_uptime


@dataclass
class BlockSensorDescription(BlockEntityDescription, SensorEntityDescription):
    """Class to describe a BLOCK sensor."""


@dataclass
class RpcSensorDescription(RpcEntityDescription, SensorEntityDescription):
    """Class to describe a RPC sensor."""


@dataclass
class RestSensorDescription(RestEntityDescription, SensorEntityDescription):
    """Class to describe a REST sensor."""


SENSORS: Final = {
    ("device", "battery"): BlockSensorDescription(
        key="device|battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda settings, _: settings.get("external_power") == 1,
        available=lambda block: cast(int, block.battery) != -1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("device", "deviceTemp"): BlockSensorDescription(
        key="device|deviceTemp",
        name="Device Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("emeter", "current"): BlockSensorDescription(
        key="emeter|current",
        name="Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value=lambda value: value,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("light", "power"): BlockSensorDescription(
        key="light|power",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("device", "power"): BlockSensorDescription(
        key="device|power",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "power"): BlockSensorDescription(
        key="emeter|power",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "voltage"): BlockSensorDescription(
        key="device|voltage",
        name="Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("emeter", "voltage"): BlockSensorDescription(
        key="emeter|voltage",
        name="Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "powerFactor"): BlockSensorDescription(
        key="emeter|powerFactor",
        name="Power Factor",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda value: round(value * 100, 1),
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "power"): BlockSensorDescription(
        key="relay|power",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("roller", "rollerPower"): BlockSensorDescription(
        key="roller|rollerPower",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "energy"): BlockSensorDescription(
        key="device|energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("emeter", "energy"): BlockSensorDescription(
        key="emeter|energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energy) != -1,
    ),
    ("emeter", "energyReturned"): BlockSensorDescription(
        key="emeter|energyReturned",
        name="Energy Returned",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energyReturned) != -1,
    ),
    ("light", "energy"): BlockSensorDescription(
        key="light|energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ("relay", "energy"): BlockSensorDescription(
        key="relay|energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("roller", "rollerEnergy"): BlockSensorDescription(
        key="roller|rollerEnergy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda value: round(value / 60 / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("sensor", "concentration"): BlockSensorDescription(
        key="sensor|concentration",
        name="Gas Concentration",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "temp"): BlockSensorDescription(
        key="sensor|temp",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("sensor", "extTemp"): BlockSensorDescription(
        key="sensor|extTemp",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.extTemp) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "humidity"): BlockSensorDescription(
        key="sensor|humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda value: round(value, 1),
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.humidity) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "luminosity"): BlockSensorDescription(
        key="sensor|luminosity",
        name="Luminosity",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.luminosity) != -1,
    ),
    ("sensor", "tilt"): BlockSensorDescription(
        key="sensor|tilt",
        name="Tilt",
        native_unit_of_measurement=DEGREE,
        icon="mdi:angle-acute",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "totalWorkTime"): BlockSensorDescription(
        key="relay|totalWorkTime",
        name="Lamp Life",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:progress-wrench",
        value=lambda value: round(100 - (value / 3600 / SHAIR_MAX_WORK_HOURS), 1),
        extra_state_attributes=lambda block: {
            "Operational hours": round(cast(int, block.totalWorkTime) / 3600, 1)
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("adc", "adc"): BlockSensorDescription(
        key="adc|adc",
        name="ADC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda value: round(value, 2),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "sensorOp"): BlockSensorDescription(
        key="sensor|sensorOp",
        name="Operation",
        icon="mdi:cog-transfer",
        value=lambda value: value,
        extra_state_attributes=lambda block: {"self_test": block.selfTest},
    ),
}

REST_SENSORS: Final = {
    "rssi": RestSensorDescription(
        key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value=lambda status, _: status["wifi_sta"]["rssi"],
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": RestSensorDescription(
        key="uptime",
        name="Uptime",
        value=lambda status, last: get_device_uptime(status["uptime"], last),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


RPC_SENSORS: Final = {
    "power": RpcSensorDescription(
        key="switch",
        sub_key="apower",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        value=lambda status, _: round(float(status), 1),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voltage": RpcSensorDescription(
        key="switch",
        sub_key="voltage",
        name="Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda status, _: round(float(status), 1),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "energy": RpcSensorDescription(
        key="switch",
        sub_key="aenergy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value=lambda status, _: round(status["total"] / 1000, 2),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "temperature": RpcSensorDescription(
        key="switch",
        sub_key="temperature",
        name="Device Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda status, _: round(status["tC"], 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_0": RpcSensorDescription(
        key="temperature",
        sub_key="tC",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda status, _: round(status, 1),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    "rssi": RpcSensorDescription(
        key="wifi",
        sub_key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "uptime": RpcSensorDescription(
        key="sys",
        sub_key="uptime",
        name="Uptime",
        value=get_device_uptime,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "humidity_0": RpcSensorDescription(
        key="humidity",
        sub_key="rh",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda status, _: round(status, 1),
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    "battery": RpcSensorDescription(
        key="devicepower:0",
        sub_key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda status, _: status["percent"],
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "voltmeter": RpcSensorDescription(
        key="voltmeter",
        sub_key="voltage",
        name="Voltmeter",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda status, _: round(float(status), 2),
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        available=lambda status: status is not None,
    ),
    "analoginput": RpcSensorDescription(
        key="analoginput",
        sub_key="percent",
        name="Analog Input",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
}


def _build_block_description(entry: RegistryEntry) -> BlockSensorDescription:
    """Build description when restoring block attribute entities."""
    return BlockSensorDescription(
        key="",
        name="",
        icon=entry.original_icon,
        native_unit_of_measurement=entry.unit_of_measurement,
        device_class=entry.original_device_class,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) == 2:
        if config_entry.data[CONF_SLEEP_PERIOD]:
            async_setup_entry_rpc(
                hass,
                config_entry,
                async_add_entities,
                RPC_SENSORS,
                RpcSleepingSensor,
            )
        else:
            async_setup_entry_rpc(
                hass, config_entry, async_add_entities, RPC_SENSORS, RpcSensor
            )
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSleepingSensor,
            _build_block_description,
        )
    else:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSensor,
            _build_block_description,
        )
        async_setup_entry_rest(
            hass, config_entry, async_add_entities, REST_SENSORS, RestSensor
        )


class BlockSensor(ShellyBlockAttributeEntity, SensorEntity):
    """Represent a block sensor."""

    entity_description: BlockSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, block, attribute, description)

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class RestSensor(ShellyRestAttributeEntity, SensorEntity):
    """Represent a REST sensor."""

    entity_description: RestSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class RpcSensor(ShellyRpcAttributeEntity, SensorEntity):
    """Represent a RPC sensor."""

    entity_description: RpcSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class BlockSleepingSensor(ShellySleepingBlockAttributeEntity, SensorEntity):
    """Represent a block sleeping sensor."""

    entity_description: BlockSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockSensorDescription,
        entry: RegistryEntry | None = None,
        sensors: Mapping[tuple[str, str], BlockSensorDescription] | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry, sensors)

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.block is not None:
            return self.attribute_value

        return self.last_state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.block is not None:
            return self.entity_description.native_unit_of_measurement

        return self.last_unit


class RpcSleepingSensor(ShellySleepingRpcAttributeEntity, SensorEntity):
    """Represent a RPC sleeping sensor."""

    entity_description: RpcSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.coordinator.device.initialized:
            return self.attribute_value

        return self.last_state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.coordinator.device.initialized:
            return self.entity_description.native_unit_of_measurement

        return self.last_unit
