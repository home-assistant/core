"""Sensor platform for anglian_water."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyanglianwater import AnglianWater

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AnglianWaterConfigEntry
from .coordinator import AnglianWaterDataUpdateCoordinator
from .entity import AnglianWaterEntity


@dataclass(frozen=True, kw_only=True)
class AnglianWaterEntityDescription(SensorEntityDescription):
    """Describes Anglian Water sensor entity."""

    value_fn: Callable[[AnglianWater], StateType]


SENSORS: tuple[AnglianWaterEntityDescription, ...] = (
    AnglianWaterEntityDescription(
        key="previous_consumption",
        translation_key="previous_consumption",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda aw: aw.current_usage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnglianWaterConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_devices(
        AnglianWaterSensor(
            coordinator=entry.runtime_data.coordinator,
            description=sensor,
        )
        for sensor in SENSORS
    )


class AnglianWaterSensor(AnglianWaterEntity, SensorEntity):
    """anglian_water Sensor entity."""

    entity_description: AnglianWaterEntityDescription

    def __init__(
        self,
        coordinator: AnglianWaterDataUpdateCoordinator,
        description: AnglianWaterEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.client)
