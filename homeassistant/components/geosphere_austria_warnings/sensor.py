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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import GeoSphereConfigEntry, GeoSphereData
from .entity import GeoSphereEntity

PARALLEL_UPDATES = 0

LEVEL_NONE = "none"


def _max_level(active_warnings: list[WeatherWarning]) -> str:
    """Return the highest level of the active warnings."""
    if not active_warnings:
        return LEVEL_NONE
    return max(warning.level for warning in active_warnings).name.lower()


# return max numeric warn level for current and advance warnings
def _max_numeric_level(warnings: list[WeatherWarning]) -> int:
    """Return the highest warning level as an integer."""
    return max((warning.level.value for warning in warnings), default=0)


def _warning_attributes(
    data: GeoSphereData,
    warnings: list[WeatherWarning],
) -> Mapping[str, Any]:
    """Return DWD-style warning attributes."""
    municipality = data.location_warnings.municipality

    sorted_warnings = sorted(
        warnings,
        key=lambda warning: (
            -warning.level.value,
            warning.start,
            str(warning.warning_id),
            str(warning.change_id),
            str(warning.course_id),
        ),
    )

    attributes: dict[str, Any] = {
        "municipality": municipality.name,
        "warning_count": len(sorted_warnings),
    }

    for index, warning in enumerate(sorted_warnings, start=1):
        attributes[f"warning_{index}"] = {
            "level": warning.level.value,
            "color": warning.level.name.lower(),
            "type": warning.warning_type.value,
            "name": warning.warning_type.name.lower(),
            "start": warning.start.isoformat(),
            "end": warning.end.isoformat(),
            "description": warning.text,
            "impacts": warning.impacts,
            "instruction": warning.recommendations,
            "meteo_text": warning.meteo_text,
            "update_reason": warning.update_reason,
            "warning_id": warning.warning_id,
            "change_id": warning.change_id,
            "course_id": warning.course_id,
        }

    return attributes


@dataclass(frozen=True, kw_only=True)
class GeoSphereSensorDescription(SensorEntityDescription):
    """Describes a GeoSphere Austria Warnings sensor."""

    warnings_fn: Callable[[GeoSphereData], list[WeatherWarning]]
    value_fn: Callable[[list[WeatherWarning]], StateType]
    attributes_fn: (
        Callable[
            [GeoSphereData, list[WeatherWarning]],
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
        value_fn=_max_level,
    ),
    GeoSphereSensorDescription(
        key="active_warnings",
        translation_key="active_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        warnings_fn=lambda data: data.active_warnings,
        value_fn=len,
    ),
    GeoSphereSensorDescription(
        key="current_warning_level",
        translation_key="current_warning_level",
        warnings_fn=lambda data: data.active_warnings,
        value_fn=_max_numeric_level,
        attributes_fn=_warning_attributes,
    ),
    GeoSphereSensorDescription(
        key="advance_warning_level",
        translation_key="advance_warning_level",
        warnings_fn=lambda data: data.advance_warnings,
        value_fn=_max_numeric_level,
        attributes_fn=_warning_attributes,
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
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        warnings = self.entity_description.warnings_fn(self.coordinator.data)
        return self.entity_description.value_fn(warnings)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return warning details as entity attributes."""
        warnings = self.entity_description.warnings_fn(self.coordinator.data)

        if self.entity_description.attributes_fn is None:
            return {}

        return self.entity_description.attributes_fn(
            self.coordinator.data,
            warnings,
        )
