"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from intellifire4py import IntellifirePollData
import pytz

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN


class IntellifireSensor(CoordinatorEntity, SensorEntity):
    """Define a generic class for Sensors."""

    # Define types
    coordinator: IntellifireDataUpdateCoordinator
    entity_description: IntellifireSensorEntityDescription
    _attr_attribution = "Data provided by unpublished Intellifire API"

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        description: IntellifireSensorEntityDescription,
    ) -> None:
        """Init the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description

        # Set the Display name the User will see
        self._attr_name = f"Fireplace {description.name}"
        self._attr_unique_id = f"{description.key}_{coordinator.api.data.serial}"
        # Configure the Device Info
        self._attr_device_info = self.coordinator.device_info

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state."""
        # return self.entity_description.value_fn(self.coordinator.api.data)
        return self.entity_description.value_fn(self.coordinator)


def _time_remaining_to_timestamp(coordinator: IntellifireDataUpdateCoordinator) -> datetime | None:
    """Define a sensor that takes into account timezone."""
    seconds_offset = coordinator.api.data.timeremaining_s

    # If disabled return None - else return a timestamp with correct TZ info
    if seconds_offset == 0:
        return None

    return datetime.now().replace(
        tzinfo = pytz.timezone(coordinator.hass.config.time_zone)
    ) + timedelta(seconds=seconds_offset)


@dataclass
class IntellifireSensorRequiredKeysMixin:
    """Mixin for required keys."""

    # Although sensors could have a variety of different return values,
    # all the ones below are only returning ints
    value_fn: Callable[[IntellifireDataUpdateCoordinator], int | str | datetime | None ]


@dataclass
class IntellifireSensorEntityDescription(
    SensorEntityDescription, IntellifireSensorRequiredKeysMixin
):
    """Describes a sensor sensor entity."""

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Define setup entry call."""

    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntellifireSensor(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_SENSORS
    )

INTELLIFIRE_SENSORS: tuple[IntellifireSensorEntityDescription, ...] = (
    IntellifireSensorEntityDescription(
        key="flame_height",
        icon="mdi:fire-circle",
        name="Flame Height",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord: coord.api.data.flameheight,
    ),
    IntellifireSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda coord: coord.api.data.temperature_c,
    ),
    IntellifireSensorEntityDescription(
        key="target_temp",
        name="Target Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda coord: coord.api.data.thermostat_setpoint_c,
    ),
    IntellifireSensorEntityDescription(
        key="fan_speed",
        icon="mdi:fan",
        name="Fan Speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord: coord.api.data.fanspeed,
    ),
    IntellifireSensorEntityDescription(
        key="timer_end_timestamp",
        icon="mdi:timer-sand",
        name="Timer End",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord: _time_remaining_to_timestamp(coord)

    ),
)
