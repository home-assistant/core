"""Sensor for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_PLATFORM,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.typing import StateType

from .const import CONF_SLEEP_PERIOD
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
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
    get_entity_rpc_device_info,
)
from .utils import (
    async_remove_orphaned_entities,
    get_block_channel_name,
    get_blu_trv_device_info,
    get_device_entry_gen,
    get_device_uptime,
    get_rpc_channel_name,
    get_shelly_air_lamp_life,
    get_virtual_component_unit,
    is_rpc_wifi_stations_disabled,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockSensorDescription(BlockEntityDescription, SensorEntityDescription):
    """Class to describe a BLOCK sensor."""


@dataclass(frozen=True, kw_only=True)
class RpcSensorDescription(RpcEntityDescription, SensorEntityDescription):
    """Class to describe a RPC sensor."""

    emeter_phase: str | None = None


@dataclass(frozen=True, kw_only=True)
class RestSensorDescription(RestEntityDescription, SensorEntityDescription):
    """Class to describe a REST sensor."""


class RpcSensor(ShellyRpcAttributeEntity, SensorEntity):
    """Represent a RPC sensor."""

    entity_description: RpcSensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSensorDescription,
    ) -> None:
        """Initialize select."""
        super().__init__(coordinator, key, attribute, description)

        if not description.role:
            if hasattr(self, "_attr_name"):
                delattr(self, "_attr_name")

            if (
                channel_name := get_rpc_channel_name(coordinator.device, key)
            ) is not None:
                self._attr_translation_placeholders = {"channel_name": channel_name}

            if "channel_name" in self.translation_placeholders and (
                translation_key := description.translation_key
                or (
                    description.device_class
                    if self._default_to_device_class_name()
                    else None
                )
            ):
                self._attr_translation_key = f"{translation_key}_with_channel_name"

        if self.option_map:
            self._attr_options = list(self.option_map.values())

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        attribute_value = self.attribute_value

        if not self.option_map:
            return attribute_value

        if not isinstance(attribute_value, str):
            return None

        return self.option_map[attribute_value]


class RpcEnergyConsumedSensor(RpcSensor):
    """Represent a RPC energy consumed sensor."""

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        total_energy = self.status["aenergy"]["total"]

        if not isinstance(total_energy, float):
            return None

        if not isinstance(self.attribute_value, float):
            return None

        return total_energy - self.attribute_value


class RpcPresenceSensor(RpcSensor):
    """Represent a RPC presence sensor."""

    @property
    def available(self) -> bool:
        """Available."""
        available = super().available

        return available and self.coordinator.device.config[self.key]["enable"]


class RpcEmeterPhaseSensor(RpcSensor):
    """Represent a RPC energy meter phase sensor."""

    entity_description: RpcSensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSensorDescription,
    ) -> None:
        """Initialize select."""
        super().__init__(coordinator, key, attribute, description)

        self._attr_device_info = get_entity_rpc_device_info(
            coordinator, key, emeter_phase=description.emeter_phase
        )


class RpcBluTrvSensor(RpcSensor):
    """Represent a RPC BluTrv sensor."""

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSensorDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, key, attribute, description)
        ble_addr: str = coordinator.device.config[key]["addr"]
        fw_ver = coordinator.device.status[key].get("fw_ver")
        self._attr_device_info = get_blu_trv_device_info(
            coordinator.device.config[key], ble_addr, coordinator.mac, fw_ver
        )


SENSORS: dict[tuple[str, str], BlockSensorDescription] = {
    ("device", "battery"): BlockSensorDescription(
        key="device|battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda settings, _: settings.get("external_power") == 1,
        available=lambda block: cast(int, block.battery) != -1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("device", "deviceTemp"): BlockSensorDescription(
        key="device|deviceTemp",
        translation_key="device_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("emeter", "current"): BlockSensorDescription(
        key="emeter|current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "neutralCurrent"): BlockSensorDescription(
        key="device|neutralCurrent",
        translation_key="neutral_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("light", "power"): BlockSensorDescription(
        key="light|power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("device", "power"): BlockSensorDescription(
        key="device|power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "power"): BlockSensorDescription(
        key="emeter|power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "voltage"): BlockSensorDescription(
        key="device|voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("emeter", "voltage"): BlockSensorDescription(
        key="emeter|voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "powerFactor"): BlockSensorDescription(
        key="emeter|powerFactor",
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "power"): BlockSensorDescription(
        key="relay|power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("roller", "rollerPower"): BlockSensorDescription(
        key="roller|rollerPower",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "energy"): BlockSensorDescription(
        key="device|energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("emeter", "energy"): BlockSensorDescription(
        key="emeter|energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energy) != -1,
    ),
    ("emeter", "energyReturned"): BlockSensorDescription(
        key="emeter|energyReturned",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energyReturned) != -1,
    ),
    ("light", "energy"): BlockSensorDescription(
        key="light|energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ("relay", "energy"): BlockSensorDescription(
        key="relay|energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("roller", "rollerEnergy"): BlockSensorDescription(
        key="roller|rollerEnergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("sensor", "concentration"): BlockSensorDescription(
        key="sensor|concentration",
        translation_key="gas_concentration",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "temp"): BlockSensorDescription(
        key="sensor|temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("sensor", "extTemp"): BlockSensorDescription(
        key="sensor|extTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.extTemp) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "humidity"): BlockSensorDescription(
        key="sensor|humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.humidity) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "luminosity"): BlockSensorDescription(
        key="sensor|luminosity",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.luminosity) != -1,
    ),
    ("sensor", "tilt"): BlockSensorDescription(
        key="sensor|tilt",
        translation_key="tilt",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "totalWorkTime"): BlockSensorDescription(
        key="relay|totalWorkTime",
        translation_key="lamp_life",
        native_unit_of_measurement=PERCENTAGE,
        value=get_shelly_air_lamp_life,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("adc", "adc"): BlockSensorDescription(
        key="adc|adc",
        translation_key="adc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "sensorOp"): BlockSensorDescription(
        key="sensor|sensorOp",
        translation_key="operation",
        device_class=SensorDeviceClass.ENUM,
        options=["warmup", "normal", "fault"],
        value=lambda value: None if value == "unknown" else value,
    ),
    ("valve", "valve"): BlockSensorDescription(
        key="valve|valve",
        translation_key="valve_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "checking",
            "closed",
            "closing",
            "failure",
            "opened",
            "opening",
        ],
        value=lambda value: None if value == "unknown" else value,
        entity_category=EntityCategory.DIAGNOSTIC,
        removal_condition=lambda _, block: block.valve == "not_connected",
    ),
    ("sensor", "gas"): BlockSensorDescription(
        key="sensor|gas",
        translation_key="gas_detected",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "none",
            "mild",
            "heavy",
            "test",
        ],
        value=lambda value: None if value == "unknown" else value,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("sensor", "selfTest"): BlockSensorDescription(
        key="sensor|selfTest",
        translation_key="self_test",
        device_class=SensorDeviceClass.ENUM,
        options=["not_completed", "completed", "running", "pending"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

REST_SENSORS: Final = {
    "rssi": RestSensorDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value=lambda status, _: status["wifi_sta"]["rssi"],
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": RestSensorDescription(
        key="uptime",
        translation_key="last_restart",
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
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_em1": RpcSensorDescription(
        key="em1",
        sub_key="act_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_light": RpcSensorDescription(
        key="light",
        sub_key="apower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="apower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_cct": RpcSensorDescription(
        key="cct",
        sub_key="apower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_rgb": RpcSensorDescription(
        key="rgb",
        sub_key="apower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_rgbw": RpcSensorDescription(
        key="rgbw",
        sub_key="apower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_act_power": RpcSensorDescription(
        key="em",
        sub_key="a_act_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_act_power": RpcSensorDescription(
        key="em",
        sub_key="b_act_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_act_power": RpcSensorDescription(
        key="em",
        sub_key="c_act_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "total_act_power": RpcSensorDescription(
        key="em",
        sub_key="total_act_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="a_aprt_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="b_aprt_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="c_aprt_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "aprt_power_em1": RpcSensorDescription(
        key="em1",
        sub_key="aprt_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "total_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="total_aprt_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pf_em1": RpcSensorDescription(
        key="em1",
        sub_key="pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_pf": RpcSensorDescription(
        key="em",
        sub_key="a_pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_pf": RpcSensorDescription(
        key="em",
        sub_key="b_pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_pf": RpcSensorDescription(
        key="em",
        sub_key="c_pf",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "voltage": RpcSensorDescription(
        key="switch",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_em1": RpcSensorDescription(
        key="em1",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_light": RpcSensorDescription(
        key="light",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_cct": RpcSensorDescription(
        key="cct",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_rgb": RpcSensorDescription(
        key="rgb",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_rgbw": RpcSensorDescription(
        key="rgbw",
        sub_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_voltage": RpcSensorDescription(
        key="em",
        sub_key="a_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_voltage": RpcSensorDescription(
        key="em",
        sub_key="b_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_voltage": RpcSensorDescription(
        key="em",
        sub_key="c_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "current": RpcSensorDescription(
        key="switch",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_em1": RpcSensorDescription(
        key="em1",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_light": RpcSensorDescription(
        key="light",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_cct": RpcSensorDescription(
        key="cct",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_rgb": RpcSensorDescription(
        key="rgb",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_rgbw": RpcSensorDescription(
        key="rgbw",
        sub_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_current": RpcSensorDescription(
        key="em",
        sub_key="a_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_current": RpcSensorDescription(
        key="em",
        sub_key="b_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_current": RpcSensorDescription(
        key="em",
        sub_key="c_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "n_current": RpcSensorDescription(
        key="em",
        sub_key="n_current",
        translation_key="neutral_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda _, status, key: status[key].get("n_current") is None,
        entity_registry_enabled_default=False,
    ),
    "total_current": RpcSensorDescription(
        key="em",
        sub_key="total_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "energy": RpcSensorDescription(
        key="switch",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "ret_energy": RpcSensorDescription(
        key="switch",
        sub_key="ret_aenergy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        removal_condition=lambda _, status, key: (
            status[key].get("ret_aenergy") is None
        ),
    ),
    "consumed_energy_switch": RpcSensorDescription(
        key="switch",
        sub_key="ret_aenergy",
        translation_key="energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        entity_class=RpcEnergyConsumedSensor,
        removal_condition=lambda _, status, key: (
            status[key].get("ret_aenergy") is None
        ),
    ),
    "energy_light": RpcSensorDescription(
        key="light",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energy_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "ret_energy_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="ret_aenergy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "consumed_energy_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="ret_aenergy",
        translation_key="energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        entity_class=RpcEnergyConsumedSensor,
    ),
    "energy_cct": RpcSensorDescription(
        key="cct",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energy_rgb": RpcSensorDescription(
        key="rgb",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energy_rgbw": RpcSensorDescription(
        key="rgbw",
        sub_key="aenergy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "total_act": RpcSensorDescription(
        key="emdata",
        sub_key="total_act",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "total_act_energy": RpcSensorDescription(
        key="em1data",
        sub_key="total_act_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "a_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="a_total_act_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="b_total_act_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="c_total_act_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "total_act_ret": RpcSensorDescription(
        key="emdata",
        sub_key="total_act_ret",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "total_act_ret_energy": RpcSensorDescription(
        key="em1data",
        sub_key="total_act_ret_energy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "a_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="a_total_act_ret_energy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="b_total_act_ret_energy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="c_total_act_ret_energy",
        translation_key="energy_returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "freq": RpcSensorDescription(
        key="switch",
        sub_key="freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "freq_em1": RpcSensorDescription(
        key="em1",
        sub_key="freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "freq_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_freq": RpcSensorDescription(
        key="em",
        sub_key="a_freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="A",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "b_freq": RpcSensorDescription(
        key="em",
        sub_key="b_freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="B",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "c_freq": RpcSensorDescription(
        key="em",
        sub_key="c_freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        emeter_phase="C",
        entity_class=RpcEmeterPhaseSensor,
    ),
    "illuminance": RpcSensorDescription(
        key="illuminance",
        sub_key="lux",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": RpcSensorDescription(
        key="switch",
        sub_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_light": RpcSensorDescription(
        key="light",
        sub_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_cct": RpcSensorDescription(
        key="cct",
        sub_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_rgb": RpcSensorDescription(
        key="rgb",
        sub_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_rgbw": RpcSensorDescription(
        key="rgbw",
        sub_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_0": RpcSensorDescription(
        key="temperature",
        sub_key="tC",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "rssi": RpcSensorDescription(
        key="wifi",
        sub_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        removal_condition=is_rpc_wifi_stations_disabled,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "uptime": RpcSensorDescription(
        key="sys",
        sub_key="uptime",
        translation_key="last_restart",
        value=get_device_uptime,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "humidity_0": RpcSensorDescription(
        key="humidity",
        sub_key="rh",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": RpcSensorDescription(
        key="devicepower",
        sub_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda status, _: status["percent"],
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        removal_condition=lambda _, status, key: (status[key]["battery"] is None),
    ),
    "voltmeter": RpcSensorDescription(
        key="voltmeter",
        sub_key="voltage",
        translation_key="voltmeter",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda status: status is not None,
    ),
    "voltmeter_value": RpcSensorDescription(
        key="voltmeter",
        sub_key="xvoltage",
        translation_key="voltmeter_value",
        removal_condition=lambda _, status, key: (status[key].get("xvoltage") is None),
        unit=lambda config: config["xvoltage"]["unit"] or None,
    ),
    "analoginput": RpcSensorDescription(
        key="input",
        sub_key="percent",
        translation_key="analog",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda config, _, key: (
            config[key]["type"] != "analog" or config[key]["enable"] is False
        ),
    ),
    "analoginput_xpercent": RpcSensorDescription(
        key="input",
        sub_key="xpercent",
        translation_key="analog_value",
        removal_condition=lambda config, status, key: (
            config[key]["type"] != "analog"
            or config[key]["enable"] is False
            or status[key].get("xpercent") is None
        ),
        unit=lambda config: config["xpercent"]["unit"] or None,
    ),
    "pulse_counter": RpcSensorDescription(
        key="input",
        sub_key="counts",
        translation_key="pulse_counter",
        native_unit_of_measurement="pulse",
        state_class=SensorStateClass.TOTAL,
        value=lambda status, _: status["total"],
        removal_condition=lambda config, _, key: (
            config[key]["type"] != "count" or config[key]["enable"] is False
        ),
    ),
    "counter_value": RpcSensorDescription(
        key="input",
        sub_key="counts",
        translation_key="counter_value",
        value=lambda status, _: status["xtotal"],
        removal_condition=lambda config, status, key: (
            config[key]["type"] != "count"
            or config[key]["enable"] is False
            or status[key]["counts"].get("xtotal") is None
        ),
        unit=lambda config: config["xcounts"]["unit"] or None,
    ),
    "counter_frequency": RpcSensorDescription(
        key="input",
        sub_key="freq",
        translation_key="counter_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda config, _, key: (
            config[key]["type"] != "count" or config[key]["enable"] is False
        ),
    ),
    "counter_frequency_value": RpcSensorDescription(
        key="input",
        sub_key="xfreq",
        translation_key="counter_frequency_value",
        removal_condition=lambda config, status, key: (
            config[key]["type"] != "count"
            or config[key]["enable"] is False
            or status[key].get("xfreq") is None
        ),
        unit=lambda config: config["xfreq"]["unit"] or None,
    ),
    "text_generic": RpcSensorDescription(
        key="text",
        sub_key="value",
        removal_condition=lambda config, _, key: not is_view_for_platform(
            config, key, SENSOR_PLATFORM
        ),
        role="generic",
    ),
    "number_generic": RpcSensorDescription(
        key="number",
        sub_key="value",
        removal_condition=lambda config, _, key: not is_view_for_platform(
            config, key, SENSOR_PLATFORM
        ),
        unit=get_virtual_component_unit,
        role="generic",
    ),
    "enum_generic": RpcSensorDescription(
        key="enum",
        sub_key="value",
        removal_condition=lambda config, _, key: not is_view_for_platform(
            config, key, SENSOR_PLATFORM
        ),
        options_fn=lambda config: config["options"],
        device_class=SensorDeviceClass.ENUM,
        role="generic",
    ),
    "valve_position": RpcSensorDescription(
        key="blutrv",
        sub_key="pos",
        translation_key="valve_position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        removal_condition=lambda config, _, key: config[key].get("enable", False)
        is False,
        entity_class=RpcBluTrvSensor,
    ),
    "blutrv_battery": RpcSensorDescription(
        key="blutrv",
        sub_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_class=RpcBluTrvSensor,
    ),
    "blutrv_rssi": RpcSensorDescription(
        key="blutrv",
        sub_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_class=RpcBluTrvSensor,
    ),
    "illuminance_illumination": RpcSensorDescription(
        key="illuminance",
        sub_key="illumination",
        translation_key="illuminance_level",
        device_class=SensorDeviceClass.ENUM,
        options=["dark", "twilight", "bright"],
    ),
    "number_current_humidity": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        role="current_humidity",
    ),
    "number_current_temperature": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        role="current_temperature",
    ),
    "number_flow_rate": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        role="flow_rate",
    ),
    "number_water_pressure": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        role="water_pressure",
    ),
    "number_water_temperature": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        role="water_temperature",
    ),
    "number_work_state": RpcSensorDescription(
        key="number",
        sub_key="value",
        translation_key="charger_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "charger_charging",
            "charger_end",
            "charger_fault",
            "charger_free",
            "charger_free_fault",
            "charger_insert",
            "charger_pause",
            "charger_wait",
        ],
        role="work_state",
    ),
    "number_energy_charge": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        role="energy_charge",
    ),
    "number_time_charge": RpcSensorDescription(
        key="number",
        sub_key="value",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
        role="time_charge",
    ),
    "presence_num_objects": RpcSensorDescription(
        key="presence",
        sub_key="num_objects",
        translation_key="detected_objects",
        state_class=SensorStateClass.MEASUREMENT,
        entity_class=RpcPresenceSensor,
    ),
    "presencezone_num_objects": RpcSensorDescription(
        key="presencezone",
        sub_key="num_objects",
        translation_key="detected_objects",
        state_class=SensorStateClass.MEASUREMENT,
        entity_class=RpcPresenceSensor,
    ),
    "object_water_consumption": RpcSensorDescription(
        key="object",
        sub_key="value",
        value=lambda status, _: float(status["counter"]["total"]),
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        role="water_consumption",
    ),
    "object_energy_consumption": RpcSensorDescription(
        key="object",
        sub_key="value",
        value=lambda status, _: float(status["counter"]["total"]),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        role="phase_info",
    ),
    "object_total_act_energy": RpcSensorDescription(
        key="object",
        sub_key="value",
        value=lambda status, _: float(status["total_act_energy"]),
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        role="phase_info",
    ),
    "object_total_power": RpcSensorDescription(
        key="object",
        sub_key="value",
        value=lambda status, _: float(status["total_power"]),
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        role="phase_info",
    ),
    "object_phase_a_voltage": RpcSensorDescription(
        key="object",
        sub_key="value",
        translation_placeholders={"channel_name": "Phase A"},
        value=lambda status, _: float(status["phase_a"]["voltage"]),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        role="phase_info",
    ),
    "object_phase_b_voltage": RpcSensorDescription(
        key="object",
        sub_key="value",
        translation_placeholders={"channel_name": "Phase B"},
        value=lambda status, _: float(status["phase_b"]["voltage"]),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        role="phase_info",
    ),
    "object_phase_c_voltage": RpcSensorDescription(
        key="object",
        sub_key="value",
        translation_placeholders={"channel_name": "Phase C"},
        value=lambda status, _: float(status["phase_c"]["voltage"]),
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        role="phase_info",
    ),
    "cury_left_level": RpcSensorDescription(
        key="cury",
        sub_key="slots",
        translation_key="left_slot_level",
        value=lambda status, _: status["left"]["vial"]["level"],
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        available=lambda status: (left := status["left"]) is not None
        and left.get("vial", {}).get("level", -1) != -1,
    ),
    "cury_left_vial": RpcSensorDescription(
        key="cury",
        sub_key="slots",
        translation_key="left_slot_vial",
        value=lambda status, _: status["left"]["vial"]["name"],
        entity_category=EntityCategory.DIAGNOSTIC,
        available=lambda status: (left := status["left"]) is not None
        and left.get("vial", {}).get("level", -1) != -1,
    ),
    "cury_right_level": RpcSensorDescription(
        key="cury",
        sub_key="slots",
        translation_key="right_slot_level",
        value=lambda status, _: status["right"]["vial"]["level"],
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        available=lambda status: (right := status["right"]) is not None
        and right.get("vial", {}).get("level", -1) != -1,
    ),
    "cury_right_vial": RpcSensorDescription(
        key="cury",
        sub_key="slots",
        translation_key="right_slot_vial",
        value=lambda status, _: status["right"]["vial"]["name"],
        entity_category=EntityCategory.DIAGNOSTIC,
        available=lambda status: (right := status["right"]) is not None
        and right.get("vial", {}).get("level", -1) != -1,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        if config_entry.data[CONF_SLEEP_PERIOD]:
            async_setup_entry_rpc(
                hass,
                config_entry,
                async_add_entities,
                RPC_SENSORS,
                RpcSleepingSensor,
            )
        else:
            coordinator = config_entry.runtime_data.rpc
            assert coordinator

            async_setup_entry_rpc(
                hass, config_entry, async_add_entities, RPC_SENSORS, RpcSensor
            )

            async_remove_orphaned_entities(
                hass,
                config_entry.entry_id,
                coordinator.mac,
                SENSOR_PLATFORM,
                coordinator.device.status,
            )
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSleepingSensor,
        )
    else:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSensor,
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

        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")

        if (
            channel_name := get_block_channel_name(coordinator.device, self.block)
        ) is not None:
            self._attr_translation_placeholders = {"channel_name": channel_name}

        if "channel_name" in self.translation_placeholders and (
            translation_key := description.translation_key
            or (
                description.device_class
                if self._default_to_device_class_name()
                else None
            )
        ):
            self._attr_translation_key = f"{translation_key}_with_channel_name"

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class RestSensor(ShellyRestAttributeEntity, SensorEntity):
    """Represent a REST sensor."""

    entity_description: RestSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        attribute: str,
        description: RestSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, attribute, description)

        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")

        if (
            channel_name := get_block_channel_name(coordinator.device, None)
        ) is not None:
            self._attr_translation_placeholders = {"channel_name": channel_name}
            if translation_key := description.translation_key or (
                description.device_class
                if self._default_to_device_class_name()
                else None
            ):
                self._attr_translation_key = f"{translation_key}_with_channel_name"

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class BlockSleepingSensor(ShellySleepingBlockAttributeEntity, RestoreSensor):
    """Represent a block sleeping sensor."""

    entity_description: BlockSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockSensorDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry)
        self.restored_data: SensorExtraStoredData | None = None

        if block is not None:
            if hasattr(self, "_attr_name"):
                delattr(self, "_attr_name")
            if (
                channel_name := get_block_channel_name(coordinator.device, block)
            ) is not None:
                self._attr_translation_placeholders = {"channel_name": channel_name}
                if translation_key := description.translation_key or (
                    description.device_class
                    if self._default_to_device_class_name()
                    else None
                ):
                    self._attr_translation_key = f"{translation_key}_with_channel_name"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.restored_data = await self.async_get_last_sensor_data()

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.block is not None:
            return self.attribute_value

        if self.restored_data is None:
            return None

        return cast(StateType, self.restored_data.native_value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.block is not None:
            return self.entity_description.native_unit_of_measurement

        if self.restored_data is None:
            return None

        return self.restored_data.native_unit_of_measurement


class RpcSleepingSensor(ShellySleepingRpcAttributeEntity, RestoreSensor):
    """Represent a RPC sleeping sensor."""

    entity_description: RpcSensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSensorDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, key, attribute, description, entry)
        self.restored_data: SensorExtraStoredData | None = None

        if coordinator.device.initialized:
            if not description.role:
                if hasattr(self, "_attr_name"):
                    delattr(self, "_attr_name")
                if (
                    channel_name := get_rpc_channel_name(coordinator.device, key)
                ) is not None:
                    self._attr_translation_placeholders = {"channel_name": channel_name}
                    if translation_key := description.translation_key or (
                        description.device_class
                        if self._default_to_device_class_name()
                        else None
                    ):
                        self._attr_translation_key = (
                            f"{translation_key}_with_channel_name"
                        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.restored_data = await self.async_get_last_sensor_data()

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.coordinator.device.initialized:
            return self.attribute_value

        if self.restored_data is None:
            return None

        return cast(StateType, self.restored_data.native_value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return self.entity_description.native_unit_of_measurement
