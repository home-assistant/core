"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime

from intellifire4py import IntellifirePollData

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


@dataclass
class IntellifireSensorRequiredKeysMixin:
    """Mixin for required keys."""

    # Although sensors could have a variety of different return values,
    # all the ones below are only returning ints
    value_fn: Callable[[IntellifirePollData], int | str]


@dataclass
class IntellifireSensorEntityDescription(
    SensorEntityDescription, IntellifireSensorRequiredKeysMixin
):
    """Describes a sensor sensor entity."""


ATTRIBUTION = "Data provided by unpublished Intellifire API"


INTELLIFIRE_SENSORS: tuple[IntellifireSensorEntityDescription, ...] = (
    IntellifireSensorEntityDescription(
        key="flame_height",
        icon="mdi:fire-circle",
        name="Flame Height",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.flameheight,
    ),
    IntellifireSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda data: data.temperature_c,
    ),
    IntellifireSensorEntityDescription(
        key="target_temp",
        name="Target Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda data: data.thermostat_setpoint_c,
    ),
    IntellifireSensorEntityDescription(
        key="fan_speed",
        icon="mdi:fan",
        name="Fan Speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.fanspeed,
    ),
    IntellifireSensorEntityDescription(
        key="timer_end_time",
        icon="mdi:timer-sand",
        name="Timer End",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            datetime.datetime.now() + datetime.timedelta(seconds=data.timeremaining_s)
        ).strftime("%X"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Define setup entry call."""

    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntellifireSensor(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_SENSORS
    )


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
    def native_value(self) -> int | str:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.api.data)
