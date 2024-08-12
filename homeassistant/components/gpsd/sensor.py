"""Sensor platform for GPSD integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from gps3.agps3threaded import AGPS3mechanism

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_MODE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GPSDConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLIMB = "climb"
ATTR_ELEVATION = "elevation"
ATTR_GPS_TIME = "gps_time"
ATTR_SPEED = "speed"

DEFAULT_NAME = "GPS"

_MODE_VALUES = {2: "2d_fix", 3: "3d_fix"}


@dataclass(frozen=True, kw_only=True)
class GpsdSensorDescription(SensorEntityDescription):
    """Class describing GPSD sensor entities."""

    value_fn: Callable[[AGPS3mechanism], str | None]


SENSOR_TYPES: tuple[GpsdSensorDescription, ...] = (
    GpsdSensorDescription(
        key="mode",
        translation_key="mode",
        name=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_MODE_VALUES.values()),
        value_fn=lambda agps_thread: _MODE_VALUES.get(agps_thread.data_stream.mode),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GPSDConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    def native_value(self) -> str | None:
        """Return the state of GPSD."""
        return self.entity_description.value_fn(self.agps_thread)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the GPS."""
        return {
            ATTR_LATITUDE: self.agps_thread.data_stream.lat,
            ATTR_LONGITUDE: self.agps_thread.data_stream.lon,
            ATTR_ELEVATION: self.agps_thread.data_stream.alt,
            ATTR_GPS_TIME: self.agps_thread.data_stream.time,
            ATTR_SPEED: self.agps_thread.data_stream.speed,
            ATTR_CLIMB: self.agps_thread.data_stream.climb,
            ATTR_MODE: self.agps_thread.data_stream.mode,
        }
