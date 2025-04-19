"""Sensor platform for GPSD integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from gps3.agps3threaded import AGPS3mechanism

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    ATTR_TIME,
    EntityCategory,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import GPSDConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLIMB = "climb"
ATTR_ELEVATION = "elevation"
ATTR_SPEED = "speed"
ATTR_TOTAL_SATELLITES = "total_satellites"
ATTR_USED_SATELLITES = "used_satellites"

DEFAULT_NAME = "GPS"

_MODE_VALUES = {2: "2d_fix", 3: "3d_fix"}


def count_total_satellites_fn(agps_thread: AGPS3mechanism) -> int | None:
    """Count the number of total satellites."""
    satellites = agps_thread.data_stream.satellites
    return None if satellites == "n/a" else len(satellites)


def count_used_satellites_fn(agps_thread: AGPS3mechanism) -> int | None:
    """Count the number of used satellites."""
    satellites = agps_thread.data_stream.satellites
    if satellites == "n/a":
        return None

    return sum(
        1 for sat in satellites if isinstance(sat, dict) and sat.get("used", False)
    )


@dataclass(frozen=True, kw_only=True)
class GpsdSensorDescription(SensorEntityDescription):
    """Class describing GPSD sensor entities."""

    value_fn: Callable[[AGPS3mechanism], StateType | datetime]


SENSOR_TYPES: tuple[GpsdSensorDescription, ...] = (
    GpsdSensorDescription(
        key=ATTR_MODE,
        translation_key=ATTR_MODE,
        name=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_MODE_VALUES.values()),
        value_fn=lambda agps_thread: _MODE_VALUES.get(agps_thread.data_stream.mode),
    ),
    GpsdSensorDescription(
        key=ATTR_LATITUDE,
        translation_key=ATTR_LATITUDE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agps_thread: agps_thread.data_stream.lat,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_LONGITUDE,
        translation_key=ATTR_LONGITUDE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agps_thread: agps_thread.data_stream.lon,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_ELEVATION,
        translation_key=ATTR_ELEVATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda agps_thread: agps_thread.data_stream.alt,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_TIME,
        translation_key=ATTR_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda agps_thread: dt_util.parse_datetime(
            agps_thread.data_stream.time
        ),
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_SPEED,
        translation_key=ATTR_SPEED,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda agps_thread: agps_thread.data_stream.speed,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_CLIMB,
        translation_key=ATTR_CLIMB,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda agps_thread: agps_thread.data_stream.climb,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_TOTAL_SATELLITES,
        translation_key=ATTR_TOTAL_SATELLITES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=count_total_satellites_fn,
        entity_registry_enabled_default=False,
    ),
    GpsdSensorDescription(
        key=ATTR_USED_SATELLITES,
        translation_key=ATTR_USED_SATELLITES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=count_used_satellites_fn,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GPSDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GPSD component."""
    async_add_entities(
        [
            GpsdSensor(
                config_entry.runtime_data,
                config_entry.entry_id,
                description,
            )
            for description in SENSOR_TYPES
        ]
    )


class GpsdSensor(SensorEntity):
    """Representation of a GPS receiver available via GPSD."""

    _attr_has_entity_name = True

    entity_description: GpsdSensorDescription

    def __init__(
        self,
        agps_thread: AGPS3mechanism,
        unique_id: str,
        description: GpsdSensorDescription,
    ) -> None:
        """Initialize the GPSD sensor."""
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{unique_id}-{self.entity_description.key}"

        self.agps_thread = agps_thread

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of GPSD."""
        value = self.entity_description.value_fn(self.agps_thread)
        return None if value == "n/a" else value
