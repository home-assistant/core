"""Sensors for the Elexa Guardian integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import (
    GuardianData,
    PairedSensorEntity,
    ValveControllerEntity,
    ValveControllerEntityDescription,
)
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_VALVE_STATUS,
    CONF_UID,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)

SENSOR_KIND_AVG_CURRENT = "average_current"
SENSOR_KIND_BATTERY = "battery"
SENSOR_KIND_INST_CURRENT = "instantaneous_current"
SENSOR_KIND_INST_CURRENT_DDT = "instantaneous_current_ddt"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_TRAVEL_COUNT = "travel_count"
SENSOR_KIND_UPTIME = "uptime"


@dataclass(frozen=True, kw_only=True)
class PairedSensorDescription(SensorEntityDescription):
    """Describe a Guardian paired sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]


@dataclass(frozen=True, kw_only=True)
class ValveControllerSensorDescription(
    SensorEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]


PAIRED_SENSOR_DESCRIPTIONS = (
    PairedSensorDescription(
        key=SENSOR_KIND_BATTERY,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data["battery"],
    ),
    PairedSensorDescription(
        key=SENSOR_KIND_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["temperature"],
    ),
)
VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerSensorDescription(
        key=SENSOR_KIND_AVG_CURRENT,
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        api_category=API_VALVE_STATUS,
        value_fn=lambda data: data["average_current"],
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_INST_CURRENT,
        translation_key="instantaneous_current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        api_category=API_VALVE_STATUS,
        value_fn=lambda data: data["instantaneous_current"],
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_INST_CURRENT_DDT,
        translation_key="instantaneous_current_ddt",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        api_category=API_VALVE_STATUS,
        value_fn=lambda data: data["instantaneous_current_ddt"],
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=API_SYSTEM_ONBOARD_SENSOR_STATUS,
        value_fn=lambda data: data["temperature"],
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_UPTIME,
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        api_category=API_SYSTEM_DIAGNOSTICS,
        value_fn=lambda data: data["uptime"],
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_TRAVEL_COUNT,
        translation_key="travel_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="revolutions",
        api_category=API_VALVE_STATUS,
        value_fn=lambda data: data["travel_count"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""
    data: GuardianData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def add_new_paired_sensor(uid: str) -> None:
        """Add a new paired sensor."""
        async_add_entities(
            PairedSensorSensor(
                entry, data.paired_sensor_manager.coordinators[uid], description
            )
            for description in PAIRED_SENSOR_DESCRIPTIONS
        )

    # Handle adding paired sensors after HASS startup:
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(entry.data[CONF_UID]),
            add_new_paired_sensor,
        )
    )

    # Add all valve controller-specific binary sensors:
    sensors: list[PairedSensorSensor | ValveControllerSensor] = [
        ValveControllerSensor(entry, data.valve_controller_coordinators, description)
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    ]

    # Add all paired sensor-specific binary sensors:
    sensors.extend(
        [
            PairedSensorSensor(entry, coordinator, description)
            for coordinator in data.paired_sensor_manager.coordinators.values()
            for description in PAIRED_SENSOR_DESCRIPTIONS
        ]
    )

    async_add_entities(sensors)


class PairedSensorSensor(PairedSensorEntity, SensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    entity_description: PairedSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class ValveControllerSensor(ValveControllerEntity, SensorEntity):
    """Define a generic Guardian sensor."""

    entity_description: ValveControllerSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
