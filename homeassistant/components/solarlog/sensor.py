"""Platform for solarlog sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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

from . import SolarlogConfigEntry
from .entity import SolarLogCoordinatorEntity, SolarLogInverterEntity


@dataclass(frozen=True)
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    value_fn: Callable[[float | int], float] | Callable[[datetime], datetime] = (
        lambda value: value
    )


SOLARLOG_SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="last_updated",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        translation_key="power_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        translation_key="power_dc",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        translation_key="voltage_ac",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        translation_key="voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        translation_key="yield_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        translation_key="yield_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        translation_key="yield_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        translation_key="yield_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        translation_key="yield_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        translation_key="consumption_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        translation_key="consumption_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        translation_key="consumption_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        translation_key="consumption_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        translation_key="consumption_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="self_consumption_year",
        translation_key="self_consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        translation_key="alternator_loss",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        translation_key="power_available",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        translation_key="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
)

INVERTER_SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarlogConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add solarlog entry."""
    coordinator = entry.runtime_data

    # https://github.com/python/mypy/issues/14294

    entities: list[SensorEntity] = [
        SolarLogCoordinatorSensor(coordinator, sensor)
        for sensor in SOLARLOG_SENSOR_TYPES
    ]

    device_data: dict[str, Any] = coordinator.data["devices"]

    if not device_data:
        entities.extend(
            SolarLogInverterSensor(coordinator, sensor, int(device_id))
            for device_id in device_data
            for sensor in INVERTER_SENSOR_TYPES
            if sensor.key in device_data[device_id]
        )

    async_add_entities(entities)


class SolarLogCoordinatorSensor(SolarLogCoordinatorEntity, SensorEntity):
    """Represents a SolarLog sensor."""

    entity_description: SolarLogSensorEntityDescription

    @property
    def native_value(self) -> float | datetime:
        """Return the state for this sensor."""

        val = self.coordinator.data[self.entity_description.key]
        return self.entity_description.value_fn(val)


class SolarLogInverterSensor(SolarLogInverterEntity, SensorEntity):
    """Represents a SolarLog inverter sensor."""

    entity_description: SolarLogSensorEntityDescription

    @property
    def native_value(self) -> float | datetime:
        """Return the state for this sensor."""

        val = self.coordinator.data["devices"][self.device_id][
            self.entity_description.key
        ]
        return self.entity_description.value_fn(val)
