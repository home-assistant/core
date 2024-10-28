"""Support for Radarr binary sensors."""

from __future__ import annotations

from aiopyarr import Health

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RadarrConfigEntry
from .const import HEALTH_ISSUES
from .entity import RadarrEntity

BINARY_SENSOR_TYPE = BinarySensorEntityDescription(
    key="health",
    translation_key="health",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RadarrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Radarr sensors based on a config entry."""
    coordinator = entry.runtime_data.health
    async_add_entities([RadarrBinarySensor(coordinator, BINARY_SENSOR_TYPE)])


class RadarrBinarySensor(RadarrEntity[list[Health]], BinarySensorEntity):
    """Implementation of a Radarr binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return any(report.source in HEALTH_ISSUES for report in self.coordinator.data)
