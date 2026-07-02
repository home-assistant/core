"""Sensors summarizing GeoSphere Austria weather warnings."""

from collections.abc import Callable
from dataclasses import dataclass

from pygeosphere_warnings import WeatherWarning

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import GeoSphereConfigEntry
from .entity import GeoSphereEntity

PARALLEL_UPDATES = 0

LEVEL_NONE = "none"


def _max_level(active_warnings: list[WeatherWarning]) -> str:
    """Return the highest level of the active warnings."""
    if not active_warnings:
        return LEVEL_NONE
    return max(warning.level for warning in active_warnings).name.lower()


@dataclass(frozen=True, kw_only=True)
class GeoSphereSensorDescription(SensorEntityDescription):
    """Describes a GeoSphere Austria Warnings sensor."""

    value_fn: Callable[[list[WeatherWarning]], StateType]


SENSORS: tuple[GeoSphereSensorDescription, ...] = (
    GeoSphereSensorDescription(
        key="warning_level",
        translation_key="warning_level",
        device_class=SensorDeviceClass.ENUM,
        options=[LEVEL_NONE, "yellow", "orange", "red"],
        value_fn=_max_level,
    ),
    GeoSphereSensorDescription(
        key="active_warnings",
        translation_key="active_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=len,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoSphereConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        GeoSphereSensor(coordinator, description) for description in SENSORS
    )


class GeoSphereSensor(GeoSphereEntity, SensorEntity):
    """Sensor summarizing the currently active warnings."""

    entity_description: GeoSphereSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.active_warnings)
