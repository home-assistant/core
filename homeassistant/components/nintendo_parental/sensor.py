"""Sensor platform for Nintendo Parental."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NintendoParentalConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class NintendoParentalSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo Parental sensor entities."""

    value_fn: Callable[[Device], int | float | None]
    state_attributes_fn: Callable[[Device], Mapping[str, Any] | None]


SENSOR_DESCRIPTIONS: tuple[NintendoParentalSensorEntityDescription, ...] = (
    NintendoParentalSensorEntityDescription(
        key="playing_time",
        name="used screen time",
        native_unit_of_measurement="min",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_playing_time,
        state_attributes_fn=lambda device: {"daily": device.daily_summaries[0:5]},
    ),
    NintendoParentalSensorEntityDescription(
        key="time_remaining",
        name="time remaining",
        native_unit_of_measurement="min",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_time_remaining,
        state_attributes_fn=lambda device: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if entry.runtime_data.api.devices is not None:
        async_add_devices(
            NintendoParentalSensor(entry.runtime_data, device, sensor)
            for device in entry.runtime_data.api.devices.values()
            for sensor in SENSOR_DESCRIPTIONS
        )


class NintendoParentalSensor(NintendoDevice, SensorEntity):
    """Represent a single sensor."""

    entity_description: NintendoParentalSensorEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, device=device, entity_id=description.key
        )
        self.entity_description = description

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return self.entity_description.state_attributes_fn(self._device)
