"""Sensor support for Melnor Bluetooth water timer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Device, Valve

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import (
    MelnorBluetoothBaseEntity,
    MelnorDataUpdateCoordinator,
    MelnorZoneEntity,
)


def watering_seconds_left(valve: Valve) -> float:
    """Calculate the number of minutes left in the current watering cycle."""

    seconds_remaining = (
        dt_util.utc_from_timestamp(valve.watering_end_time) - dt_util.now()
    ).seconds

    if valve.is_watering is not True or seconds_remaining > 360 * 60:
        return 0

    return seconds_remaining


@dataclass
class MelnorSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[Device], Any]


@dataclass
class MelnorZoneSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[Valve], Any]


@dataclass
class MelnorZoneSensorEntityDescription(
    SensorEntityDescription, MelnorZoneSensorEntityDescriptionMixin
):
    """Describes Melnor sensor entity."""


@dataclass
class MelnorSensorEntityDescription(
    SensorEntityDescription, MelnorSensorEntityDescriptionMixin
):
    """Describes Melnor sensor entity."""


device_sensors: list[MelnorSensorEntityDescription] = [
    MelnorSensorEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=lambda device: device.battery_level,
    ),
    MelnorSensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=lambda device: device.rssi,
    ),
]

zone_sensors: list[MelnorZoneSensorEntityDescription] = [
    MelnorZoneSensorEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        key="minutes_remaining",
        name="Time Remaining",
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=watering_seconds_left,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        MelnorSensorEntity(
            coordinator,
            description,
        )
        for description in device_sensors
    )

    entities = []
    # This device may not have 4 valves total, but the library will only expose the right number of valves
    for i in range(1, 5):
        valve = coordinator.data[f"zone{i}"]
        if valve is not None:
            for description in zone_sensors:
                entities.append(
                    MelnorZoneSensorEntity(
                        coordinator,
                        description,
                        valve,
                    ),
                )

    async_add_entities(entities)


class MelnorSensorEntity(MelnorBluetoothBaseEntity, SensorEntity):
    """Representation of a Melnor sensor."""

    entity_description: MelnorSensorEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for a Melnor device."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{self._device.mac}-{entity_description.key}"

        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.state_fn(self._device)


class MelnorZoneSensorEntity(MelnorZoneEntity, SensorEntity):
    """Representation of a Melnor sensor."""

    entity_description: MelnorZoneSensorEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        entity_description: MelnorZoneSensorEntityDescription,
        valve: Valve,
    ) -> None:
        """Initialize a sensor for a Melnor device."""
        super().__init__(coordinator, valve)

        self._attr_unique_id = (
            f"{self._device.mac}-zone{valve.id}-{entity_description.key}"
        )

        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.state_fn(self._valve)
