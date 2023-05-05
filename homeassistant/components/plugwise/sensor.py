"""Plugwise Sensor component for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from plugwise import DeviceData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


@dataclass
class PlugwiseSensorBaseMixin:
    """Mixin for required Plugwise sensor base description keys."""

    value_fn: Callable[[DeviceData], float | int]


@dataclass
class PlugwiseSensorEntityDescription(SensorEntityDescription, PlugwiseSensorBaseMixin):
    """Describes Plugwise sensor entity."""

    state_class: str | None = SensorStateClass.MEASUREMENT


SENSORS: tuple[PlugwiseSensorEntityDescription, ...] = (
    PlugwiseSensorEntityDescription(
        key="setpoint",
        name="Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["sensors"]["setpoint"],
    ),
    PlugwiseSensorEntityDescription(
        key="setpoint_high",
        name="Cooling setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["sensors"]["setpoint_high"],
    ),
    PlugwiseSensorEntityDescription(
        key="setpoint_low",
        name="Heating setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["sensors"]["setpoint_low"],
    ),
    PlugwiseSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="intended_boiler_temperature",
        name="Intended boiler temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["intended_boiler_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="temperature_difference",
        name="Temperature difference",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["temperature_difference"],
    ),
    PlugwiseSensorEntityDescription(
        key="outdoor_temperature",
        name="Outdoor temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["outdoor_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="outdoor_air_temperature",
        name="Outdoor air temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["outdoor_air_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="water_temperature",
        name="Water temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["water_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="return_temperature",
        name="Return temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["return_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed",
        name="Electricity consumed",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_consumed"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced",
        name="Electricity produced",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_produced"],
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_interval",
        name="Electricity consumed interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_consumed_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_peak_interval",
        name="Electricity consumed peak interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_consumed_peak_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_off_peak_interval",
        name="Electricity consumed off peak interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_consumed_off_peak_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_interval",
        name="Electricity produced interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_produced_interval"],
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_peak_interval",
        name="Electricity produced peak interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_produced_peak_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_off_peak_interval",
        name="Electricity produced off peak interval",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["electricity_produced_off_peak_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_point",
        name="Electricity consumed point",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_consumed_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_off_peak_point",
        name="Electricity consumed off peak point",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_consumed_off_peak_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_peak_point",
        name="Electricity consumed peak point",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_consumed_peak_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_off_peak_cumulative",
        name="Electricity consumed off peak cumulative",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["sensors"][
            "electricity_consumed_off_peak_cumulative"
        ],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_consumed_peak_cumulative",
        name="Electricity consumed peak cumulative",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["sensors"]["electricity_consumed_peak_cumulative"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_point",
        name="Electricity produced point",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_produced_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_off_peak_point",
        name="Electricity produced off peak point",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_produced_off_peak_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_peak_point",
        name="Electricity produced peak point",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_produced_peak_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_off_peak_cumulative",
        name="Electricity produced off peak cumulative",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["sensors"][
            "electricity_produced_off_peak_cumulative"
        ],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_produced_peak_cumulative",
        name="Electricity produced peak cumulative",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["sensors"]["electricity_produced_peak_cumulative"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_one_consumed",
        name="Electricity phase one consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_one_consumed"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_two_consumed",
        name="Electricity phase two consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_two_consumed"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_three_consumed",
        name="Electricity phase three consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_three_consumed"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_one_produced",
        name="Electricity phase one produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_one_produced"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_two_produced",
        name="Electricity phase two produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_two_produced"],
    ),
    PlugwiseSensorEntityDescription(
        key="electricity_phase_three_produced",
        name="Electricity phase three produced",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["electricity_phase_three_produced"],
    ),
    PlugwiseSensorEntityDescription(
        key="voltage_phase_one",
        name="Voltage phase one",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["voltage_phase_one"],
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="voltage_phase_two",
        name="Voltage phase two",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["voltage_phase_two"],
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="voltage_phase_three",
        name="Voltage phase three",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["voltage_phase_three"],
        entity_registry_enabled_default=False,
    ),
    PlugwiseSensorEntityDescription(
        key="gas_consumed_interval",
        name="Gas consumed interval",
        icon="mdi:meter-gas",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["gas_consumed_interval"],
    ),
    PlugwiseSensorEntityDescription(
        key="gas_consumed_cumulative",
        name="Gas consumed cumulative",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["gas_consumed_cumulative"],
    ),
    PlugwiseSensorEntityDescription(
        key="net_electricity_point",
        name="Net electricity point",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["net_electricity_point"],
    ),
    PlugwiseSensorEntityDescription(
        key="net_electricity_cumulative",
        name="Net electricity cumulative",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["sensors"]["net_electricity_cumulative"],
    ),
    PlugwiseSensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["battery"],
    ),
    PlugwiseSensorEntityDescription(
        key="illuminance",
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["illuminance"],
    ),
    PlugwiseSensorEntityDescription(
        key="modulation_level",
        name="Modulation level",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["modulation_level"],
    ),
    PlugwiseSensorEntityDescription(
        key="valve_position",
        name="Valve position",
        icon="mdi:valve",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["valve_position"],
    ),
    PlugwiseSensorEntityDescription(
        key="water_pressure",
        name="Water pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["water_pressure"],
    ),
    PlugwiseSensorEntityDescription(
        key="humidity",
        name="Relative humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["humidity"],
    ),
    PlugwiseSensorEntityDescription(
        key="dhw_temperature",
        name="DHW temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["dhw_temperature"],
    ),
    PlugwiseSensorEntityDescription(
        key="domestic_hot_water_setpoint",
        name="DHW setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["sensors"]["domestic_hot_water_setpoint"],
    ),
    PlugwiseSensorEntityDescription(
        key="maximum_boiler_temperature",
        name="Maximum boiler temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["maximum_boiler_temperature"]["setpoint"],  # type: ignore [index]
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[PlugwiseSensorEntity] = []
    for device_id, device in coordinator.data.devices.items():
        if "sensors" not in device:
            continue
        for description in SENSORS:
            if description.key not in device["sensors"]:
                continue

            entities.append(
                PlugwiseSensorEntity(
                    coordinator,
                    device_id,
                    description,
                )
            )

    async_add_entities(entities)


class PlugwiseSensorEntity(PlugwiseEntity, SensorEntity):
    """Represent Plugwise Sensors."""

    entity_description: PlugwiseSensorEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"

    @property
    def native_value(self) -> int | float:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.device)
