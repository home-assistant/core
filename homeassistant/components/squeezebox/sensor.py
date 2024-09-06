"""Platform for sensor integration for squeezebox."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SqueezeboxConfigEntry
from .const import (
    STATUS_SENSOR_INFO_TOTAL_ALBUMS,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS,
    STATUS_SENSOR_INFO_TOTAL_DURATION,
    STATUS_SENSOR_INFO_TOTAL_GENRES,
    STATUS_SENSOR_INFO_TOTAL_SONGS,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_NEWPLUGINS,
    STATUS_SENSOR_NEWVERSION,
    STATUS_SENSOR_OTHER_PLAYER_COUNT,
    STATUS_SENSOR_PLAYER_COUNT,
)
from .entity import LMSStatusEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_ALBUMS,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:album",
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_ARTISTS,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:account-music",
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_DURATION,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_GENRES,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:drama-masks",
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_SONGS,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:file-music",
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_LASTSCAN,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_NEWPLUGINS,
        entity_registry_visible_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_NEWVERSION,
        entity_registry_visible_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_PLAYER_COUNT,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:folder-play",
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_OTHER_PLAYER_COUNT,
        state_class=SensorStateClass.TOTAL,
        entity_registry_visible_default=False,
        icon="mdi:folder-play-outline",
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    async_add_entities(
        ServerStatusSensor(entry.runtime_data.coordinator, description)
        for description in SENSORS
    )


class ServerStatusSensor(LMSStatusEntity, SensorEntity):
    """LMS Status based sensor from LMS via cooridnatior."""

    @property
    def native_value(self) -> StateType:
        """LMS Status directly from coordinator data."""
        return cast(StateType, self.coordinator.data[self.entity_description.key])
