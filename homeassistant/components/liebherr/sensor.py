"""Sensor platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyliebherrhomeapi import TemperatureControl, TemperatureUnit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import LiebherrZoneEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LiebherrSensorEntityDescription(SensorEntityDescription):
    """Describes Liebherr sensor entity."""

    value_fn: Callable[[TemperatureControl], StateType]
    unit_fn: Callable[[TemperatureControl], str]


SENSOR_TYPES: tuple[LiebherrSensorEntityDescription, ...] = (
    LiebherrSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda control: control.value,
        unit_fn=lambda control: (
            UnitOfTemperature.FAHRENHEIT
            if control.unit == TemperatureUnit.FAHRENHEIT
            else UnitOfTemperature.CELSIUS
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr sensor entities."""
    coordinators = entry.runtime_data
    async_add_entities(
        LiebherrSensor(
            coordinator=coordinator,
            zone_id=temp_control.zone_id,
            description=description,
        )
        for coordinator in coordinators.values()
        for temp_control in coordinator.data.get_temperature_controls().values()
        for description in SENSOR_TYPES
    )


class LiebherrSensor(LiebherrZoneEntity, SensorEntity):
    """Representation of a Liebherr sensor."""

    entity_description: LiebherrSensorEntityDescription

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        zone_id: int,
        description: LiebherrSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, zone_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}_{zone_id}"

        # If device has only one zone, use model name instead of zone name
        temp_controls = coordinator.data.get_temperature_controls()
        if len(temp_controls) == 1:
            self._attr_name = None
        else:
            # Set translation key based on zone position for multi-zone devices
            self._attr_translation_key = self._get_zone_translation_key()

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if (temp_control := self.temperature_control) is None:
            return None
        return self.entity_description.unit_fn(temp_control)

    @property
    def native_value(self) -> StateType:
        """Return the current value."""
        # temperature_control is guaranteed to exist when entity is available
        assert self.temperature_control is not None
        return self.entity_description.value_fn(self.temperature_control)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.temperature_control is not None
