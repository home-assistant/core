"""Support for Lidarr binary sensors."""

from __future__ import annotations

from aiopyarr import Health

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LidarrEntity
from .const import DOMAIN, HEALTH_ISSUES

BINARY_SENSOR_TYPE = BinarySensorEntityDescription(
    key="health",
    translation_key="health",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lidarr sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["health"]
    async_add_entities([LidarrBinarySensor(coordinator, BINARY_SENSOR_TYPE)])


class LidarrBinarySensor(LidarrEntity[list[Health]], BinarySensorEntity):
    """Implementation of a Lidarr binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return any(report.source in HEALTH_ISSUES for report in self.coordinator.data)
