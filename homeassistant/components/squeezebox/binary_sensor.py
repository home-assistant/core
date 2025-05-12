"""Binary sensor platform for Squeezebox integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SqueezeboxConfigEntry
from .const import STATUS_SENSOR_NEEDSRESTART, STATUS_SENSOR_RESCAN
from .entity import LMSStatusEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_RESCAN,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_NEEDSRESTART,
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    async_add_entities(
        ServerStatusBinarySensor(entry.runtime_data.coordinator, description)
        for description in SENSORS
    )


class ServerStatusBinarySensor(LMSStatusEntity, BinarySensorEntity):
    """LMS Status based sensor from LMS via cooridnatior."""

    @property
    def is_on(self) -> bool:
        """LMS Status directly from coordinator data."""
        return bool(self.coordinator.data[self.entity_description.key])
