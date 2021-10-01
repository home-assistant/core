"""Sensors for the Elexa Guardian integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PairedSensorEntity, ValveControllerEntity
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    CONF_UID,
    DATA_COORDINATOR,
    DATA_COORDINATOR_PAIRED_SENSOR,
    DATA_UNSUB_DISPATCHER_CONNECT,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)

SENSOR_KIND_BATTERY = "battery"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"

SENSOR_DESCRIPTION_BATTERY = SensorEntityDescription(
    key=SENSOR_KIND_BATTERY,
    name="Battery",
    device_class=DEVICE_CLASS_BATTERY,
    native_unit_of_measurement=PERCENTAGE,
)
SENSOR_DESCRIPTION_TEMPERATURE = SensorEntityDescription(
    key=SENSOR_KIND_TEMPERATURE,
    name="Temperature",
    device_class=DEVICE_CLASS_TEMPERATURE,
    native_unit_of_measurement=TEMP_FAHRENHEIT,
    state_class=STATE_CLASS_MEASUREMENT,
)
SENSOR_DESCRIPTION_UPTIME = SensorEntityDescription(
    key=SENSOR_KIND_UPTIME,
    name="Uptime",
    icon="mdi:timer",
    native_unit_of_measurement=TIME_MINUTES,
)

PAIRED_SENSOR_DESCRIPTIONS = (
    SENSOR_DESCRIPTION_BATTERY,
    SENSOR_DESCRIPTION_TEMPERATURE,
)
VALVE_CONTROLLER_DESCRIPTIONS = (
    SENSOR_DESCRIPTION_TEMPERATURE,
    SENSOR_DESCRIPTION_UPTIME,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""

    @callback
    def add_new_paired_sensor(uid: str) -> None:
        """Add a new paired sensor."""
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][entry.entry_id][
            uid
        ]

        async_add_entities(
            [
                PairedSensorSensor(entry, coordinator, description)
                for description in PAIRED_SENSOR_DESCRIPTIONS
            ]
        )

    # Handle adding paired sensors after HASS startup:
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT][entry.entry_id].append(
        async_dispatcher_connect(
            hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(entry.data[CONF_UID]),
            add_new_paired_sensor,
        )
    )

    # Add all valve controller-specific binary sensors:
    sensors: list[PairedSensorSensor | ValveControllerSensor] = [
        ValveControllerSensor(
            entry, hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id], description
        )
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    ]

    # Add all paired sensor-specific binary sensors:
    sensors.extend(
        [
            PairedSensorSensor(entry, coordinator, description)
            for coordinator in hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][
                entry.entry_id
            ].values()
            for description in PAIRED_SENSOR_DESCRIPTIONS
        ]
    )

    async_add_entities(sensors)


class PairedSensorSensor(PairedSensorEntity, SensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self.entity_description.key == SENSOR_KIND_BATTERY:
            self._attr_native_value = self.coordinator.data["battery"]
        elif self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self._attr_native_value = self.coordinator.data["temperature"]


class ValveControllerSensor(ValveControllerEntity, SensorEntity):
    """Define a generic Guardian sensor."""

    async def _async_continue_entity_setup(self) -> None:
        """Register API interest (and related tasks) when the entity is added."""
        if self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self._attr_available = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
            self._attr_native_value = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].data["temperature"]
        elif self.entity_description.key == SENSOR_KIND_UPTIME:
            self._attr_available = self.coordinators[
                API_SYSTEM_DIAGNOSTICS
            ].last_update_success
            self._attr_native_value = self.coordinators[API_SYSTEM_DIAGNOSTICS].data[
                "uptime"
            ]
