"""Sensors for the Elexa Guardian integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    GuardianData,
    PairedSensorEntity,
    ValveControllerEntity,
    ValveControllerEntityDescription,
)
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    CONF_UID,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)

SENSOR_KIND_BATTERY = "battery"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"


@dataclass
class ValveControllerSensorDescription(
    SensorEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller sensor."""


PAIRED_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_KIND_BATTERY,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerSensorDescription(
        key=SENSOR_KIND_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=API_SYSTEM_ONBOARD_SENSOR_STATUS,
    ),
    ValveControllerSensorDescription(
        key=SENSOR_KIND_UPTIME,
        translation_key="uptime",
        icon="mdi:timer",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        api_category=API_SYSTEM_DIAGNOSTICS,
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

    entity_description: SensorEntityDescription

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity's underlying data."""
        if self.entity_description.key == SENSOR_KIND_BATTERY:
            self._attr_native_value = self.coordinator.data["battery"]
        elif self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self._attr_native_value = self.coordinator.data["temperature"]


class ValveControllerSensor(ValveControllerEntity, SensorEntity):
    """Define a generic Guardian sensor."""

    entity_description: ValveControllerSensorDescription

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity's underlying data."""
        if self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self._attr_native_value = self.coordinator.data["temperature"]
        elif self.entity_description.key == SENSOR_KIND_UPTIME:
            self._attr_native_value = self.coordinator.data["uptime"]
