"""Sensor support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MelnorDataUpdateCoordinator
from .models import MelnorBluetoothEntity, MelnorZoneEntity, get_entities_for_valves


def watering_seconds_left(valve: Valve) -> datetime | None:
    """Calculate the number of minutes left in the current watering cycle."""

    if valve.is_watering is not True or dt_util.now() > dt_util.utc_from_timestamp(
        valve.watering_end_time
    ):
        return None

    return dt_util.utc_from_timestamp(valve.watering_end_time)


def next_cycle(valve: Valve) -> datetime | None:
    """Return the value of the next_cycle date, only if the cycle is enabled."""

    if valve.schedule_enabled is True:
        return valve.next_cycle

    return None


@dataclass(frozen=True, kw_only=True)
class MelnorZoneSensorEntityDescription(SensorEntityDescription):
    """Describes Melnor sensor entity."""

    state_fn: Callable[[Valve], Any]


@dataclass(frozen=True, kw_only=True)
class MelnorSensorEntityDescription(SensorEntityDescription):
    """Describes Melnor sensor entity."""

    state_fn: Callable[[Device], Any]


DEVICE_ENTITY_DESCRIPTIONS: list[MelnorSensorEntityDescription] = [
    MelnorSensorEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=lambda device: device.battery_level,
    ),
    MelnorSensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        state_fn=lambda device: device.rssi,
    ),
]

ZONE_ENTITY_DESCRIPTIONS: list[MelnorZoneSensorEntityDescription] = [
    MelnorZoneSensorEntityDescription(
        device_class=SensorDeviceClass.TIMESTAMP,
        key="manual_cycle_end",
        translation_key="manual_cycle_end",
        state_fn=watering_seconds_left,
    ),
    MelnorZoneSensorEntityDescription(
        device_class=SensorDeviceClass.TIMESTAMP,
        key="next_cycle",
        translation_key="next_cycle",
        state_fn=next_cycle,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Device-level sensors
    async_add_entities(
        MelnorSensorEntity(
            coordinator,
            description,
        )
        for description in DEVICE_ENTITY_DESCRIPTIONS
    )

    # Valve/Zone-level sensors
    async_add_entities(
        get_entities_for_valves(
            coordinator,
            ZONE_ENTITY_DESCRIPTIONS,
            lambda valve, description: MelnorZoneSensorEntity(
                coordinator, description, valve
            ),
        )
    )


class MelnorSensorEntity(MelnorBluetoothEntity, SensorEntity):
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
        super().__init__(coordinator, entity_description, valve)

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.state_fn(self._valve)
