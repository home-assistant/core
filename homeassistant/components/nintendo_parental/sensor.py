"""Sensor platform for Nintendo Parental."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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


class NintendoParentalSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo Parental sensor entities."""

    value_fn: Callable[[Device], int | float | None]
    state_attributes: str


SENSOR_DESCRIPTIONS: tuple[NintendoParentalSensorEntityDescription, ...] = (
    NintendoParentalSensorEntityDescription(
        key="playing_time",
        native_unit_of_measurement="min",
        state_attributes="daily_summaries",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_playing_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if entry.runtime_data.api.devices is not None:
        for device in entry.runtime_data.api.devices.values():
            async_add_devices(
                NintendoParentalSensor(entry.runtime_data, device, sensor)
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
        self._attr_translation_placeholders = {"dev_name": device.name}

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.state_attributes == "daily_summaries":
            return {"daily": self._device.daily_summaries[0:5]}
        return None
