"""Sensor platform for Nintendo Parental."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NintendoParentalConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class NintendoParentalSensor(StrEnum):
    """Store keys for Nintendo Parental sensors."""

    PLAYING_TIME = "playing_time"
    TIME_REMAINING = "time_remaining"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo Parental sensor entities."""

    value_fn: Callable[[Device], int | float | None]


SENSOR_DESCRIPTIONS: tuple[NintendoParentalSensorEntityDescription, ...] = (
    NintendoParentalSensorEntityDescription(
        key=NintendoParentalSensor.PLAYING_TIME,
        translation_key=NintendoParentalSensor.PLAYING_TIME,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_playing_time,
    ),
    NintendoParentalSensorEntityDescription(
        key=NintendoParentalSensor.TIME_REMAINING,
        translation_key=NintendoParentalSensor.TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_time_remaining,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_devices(
        NintendoParentalSensorEntity(entry.runtime_data, device, sensor)
        for device in entry.runtime_data.api.devices.values()
        for sensor in SENSOR_DESCRIPTIONS
    )


class NintendoParentalSensorEntity(NintendoDevice, SensorEntity):
    """Represent a single sensor."""

    entity_description: NintendoParentalSensorEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self._device)
