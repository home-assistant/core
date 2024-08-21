"""Platform for solarlog sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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
from .coordinator import SolarLogCoordinator
from .entity import SolarLogCoordinatorEntity, SolarLogInverterEntity


@dataclass(frozen=True)
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    value_fn: Callable[[float | int], float] | Callable[[datetime], datetime] = (
        lambda value: value
    )


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="last_updated",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SolarLogSensorEntityDescription(
        # Inverter entity
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="power_ac",
        translation_key="power_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="power_dc",
        translation_key="power_dc",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="voltage_ac",
        translation_key="voltage_ac",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="voltage_dc",
        translation_key="voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="yield_day",
        translation_key="yield_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="yield_yesterday",
        translation_key="yield_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="yield_month",
        translation_key="yield_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="yield_year",
        translation_key="yield_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="yield_total",
        translation_key="yield_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="consumption_ac",
        translation_key="consumption_ac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="consumption_day",
        translation_key="consumption_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="consumption_yesterday",
        translation_key="consumption_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="consumption_month",
        translation_key="consumption_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="consumption_year",
        translation_key="consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity, Inverter entity
        key="consumption_total",
        translation_key="consumption_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="self_consumption_year",
        translation_key="self_consumption_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="alternator_loss",
        translation_key="alternator_loss",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="capacity",
        translation_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="efficiency",
        translation_key="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="power_available",
        translation_key="power_available",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        # Coordinator entity
        key="usage",
        translation_key="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: round(value * 100, 1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarlogConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add solarlog entry."""
    coordinator: SolarLogCoordinator = entry.runtime_data

    # https://github.com/python/mypy/issues/14294

    entities: list[SensorEntity] = [
        SolarLogCoordinatorSensor(coordinator, sensor)  # noqa: PGH003
        for sensor in SENSOR_TYPES
        if sensor.key in coordinator.data
    ]

    device_data = coordinator.data.get("devices", {})

    if device_data != {}:
        for did in device_data:
            device_id = int(did)
            if coordinator.solarlog.device_enabled(device_id):
                entities.extend(
                    SolarLogInverterSensor(coordinator, sensor, device_id)  # noqa: PGH003
                    for sensor in SENSOR_TYPES
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
