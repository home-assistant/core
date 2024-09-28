"""Platform for solarlog sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from solarlog_cli.solarlog_models import InverterData, SolarlogData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SolarlogConfigEntry
from .entity import SolarLogCoordinatorEntity, SolarLogInverterEntity


@dataclass(frozen=True, kw_only=True)
class SolarLogCoordinatorSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog coordinator sensor entity."""

    value_fn: Callable[[SolarlogData], StateType | datetime | None]


@dataclass(frozen=True, kw_only=True)
class SolarLogInverterSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog inverter sensor entity."""

    value_fn: Callable[[InverterData], float | None]


SOLARLOG_SENSOR_TYPES: tuple[SolarLogCoordinatorSensorEntityDescription, ...] = (
    SolarLogCoordinatorSensorEntityDescription(
        key="last_updated",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_updated,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="power_ac",
        translation_key="power_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_ac,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="power_dc",
        translation_key="power_dc",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_dc,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="voltage_ac",
        translation_key="voltage_ac",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voltage_ac,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="voltage_dc",
        translation_key="voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voltage_dc,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="yield_day",
        translation_key="yield_day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.yield_day,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="yield_yesterday",
        translation_key="yield_yesterday",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.yield_yesterday,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="yield_month",
        translation_key="yield_month",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.yield_month,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="yield_year",
        translation_key="yield_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.yield_year,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="yield_total",
        translation_key="yield_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda data: data.yield_total,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_ac",
        translation_key="consumption_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.consumption_ac,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_day",
        translation_key="consumption_day",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption_day,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_yesterday",
        translation_key="consumption_yesterday",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption_yesterday,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_month",
        translation_key="consumption_month",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption_month,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption_year,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="consumption_total",
        translation_key="consumption_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda data: data.consumption_total,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="self_consumption_year",
        translation_key="self_consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.self_consumption_year,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.total_power,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="alternator_loss",
        translation_key="alternator_loss",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.alternator_loss,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.capacity,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.efficiency,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="power_available",
        translation_key="power_available",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_available,
    ),
    SolarLogCoordinatorSensorEntityDescription(
        key="usage",
        translation_key="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.usage,
    ),
)

INVERTER_SENSOR_TYPES: tuple[SolarLogInverterSensorEntityDescription, ...] = (
    SolarLogInverterSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda inverter: inverter.current_power,
    ),
    SolarLogInverterSensorEntityDescription(
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=(
            lambda inverter: None
            if inverter.consumption_year is None
            else inverter.consumption_year
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarlogConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add solarlog entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        SolarLogCoordinatorSensor(coordinator, sensor)
        for sensor in SOLARLOG_SENSOR_TYPES
    ]

    device_data = coordinator.data.inverter_data

    if device_data:
        entities.extend(
            SolarLogInverterSensor(coordinator, sensor, device_id)
            for device_id in device_data
            for sensor in INVERTER_SENSOR_TYPES
        )

    async_add_entities(entities)


class SolarLogCoordinatorSensor(SolarLogCoordinatorEntity, SensorEntity):
    """Represents a SolarLog sensor."""

    entity_description: SolarLogCoordinatorSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state for this sensor."""

        return self.entity_description.value_fn(self.coordinator.data)


class SolarLogInverterSensor(SolarLogInverterEntity, SensorEntity):
    """Represents a SolarLog inverter sensor."""

    entity_description: SolarLogInverterSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state for this sensor."""

        return self.entity_description.value_fn(
            self.coordinator.data.inverter_data[self.device_id]
        )
