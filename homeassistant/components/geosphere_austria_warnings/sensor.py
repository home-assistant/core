"""Sensors summarizing GeoSphere Austria weather warnings."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, override

from pygeosphere_warnings import WeatherWarning

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import GeoSphereConfigEntry, GeoSphereData
from .entity import GeoSphereEntity
from .warnings import LEVEL_NONE, highest_warning_level, warning_sensor_attributes

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GeoSphereSensorDescription(SensorEntityDescription):
    """Describes a GeoSphere Austria Warnings sensor."""

    warnings_fn: Callable[[GeoSphereData], list[WeatherWarning]]
    value_fn: Callable[[list[WeatherWarning]], StateType]
    attributes_fn: (
        Callable[
            [list[WeatherWarning]],
            Mapping[str, Any],
        ]
        | None
    ) = None


SENSORS: tuple[GeoSphereSensorDescription, ...] = (
    GeoSphereSensorDescription(
        key="warning_level",
        translation_key="warning_level",
        device_class=SensorDeviceClass.ENUM,
        options=[LEVEL_NONE, "yellow", "orange", "red"],
        warnings_fn=lambda data: data.active_warnings,
        value_fn=highest_warning_level,
        attributes_fn=warning_sensor_attributes,
    ),
    GeoSphereSensorDescription(
        key="active_warnings",
        translation_key="active_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        warnings_fn=lambda data: data.active_warnings,
        value_fn=len,
    ),
    GeoSphereSensorDescription(
        key="advance_warning_level",
        translation_key="advance_warning_level",
        device_class=SensorDeviceClass.ENUM,
        options=[LEVEL_NONE, "yellow", "orange", "red"],
        warnings_fn=lambda data: data.advance_warnings,
        value_fn=highest_warning_level,
        attributes_fn=warning_sensor_attributes,
    ),
    GeoSphereSensorDescription(
        key="advance_warnings",
        translation_key="advance_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        warnings_fn=lambda data: data.advance_warnings,
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
    """Sensor summarizing GeoSphere Austria weather warnings."""

    _unrecorded_attributes = frozenset({MATCH_ALL})
    entity_description: GeoSphereSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        warnings = self.entity_description.warnings_fn(self.coordinator.data)
        return self.entity_description.value_fn(warnings)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return warning details as entity attributes."""
        if self.entity_description.attributes_fn is None:
            return None

        warnings = self.entity_description.warnings_fn(self.coordinator.data)
        return self.entity_description.attributes_fn(warnings)
