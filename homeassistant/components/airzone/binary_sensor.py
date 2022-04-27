"""Support for the Airzone sensors."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from aioairzone.const import (
    AZD_AIR_DEMAND,
    AZD_BATTERY_LOW,
    AZD_ERRORS,
    AZD_FLOOR_DEMAND,
    AZD_NAME,
    AZD_PROBLEMS,
    AZD_ZONES,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneEntity, AirzoneZoneEntity
from .const import DOMAIN
from .coordinator import AirzoneUpdateCoordinator


@dataclass
class AirzoneBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes airzone binary sensor entities."""

    attributes: dict[str, str] | None = None


ZONE_BINARY_SENSOR_TYPES: Final[tuple[AirzoneBinarySensorEntityDescription, ...]] = (
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        key=AZD_AIR_DEMAND,
        name="Air Demand",
    ),
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.BATTERY,
        key=AZD_BATTERY_LOW,
        name="Battery Low",
    ),
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        key=AZD_FLOOR_DEMAND,
        name="Floor Demand",
    ),
    AirzoneBinarySensorEntityDescription(
        attributes={
            "errors": AZD_ERRORS,
        },
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=AZD_PROBLEMS,
        name="Problem",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone binary sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    binary_sensors: list[AirzoneBinarySensor] = []
    for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        for description in ZONE_BINARY_SENSOR_TYPES:
            if description.key in zone_data:
                binary_sensors.append(
                    AirzoneZoneBinarySensor(
                        coordinator,
                        description,
                        entry,
                        system_zone_id,
                        zone_data,
                    )
                )

    async_add_entities(binary_sensors)


class AirzoneBinarySensor(AirzoneEntity, BinarySensorEntity):
    """Define an Airzone binary sensor."""

    entity_description: AirzoneBinarySensorEntityDescription

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return state attributes."""
        if not self.entity_description.attributes:
            return None
        return {
            key: self.get_airzone_value(val)
            for key, val in self.entity_description.attributes.items()
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.get_airzone_value(self.entity_description.key)


class AirzoneZoneBinarySensor(AirzoneZoneEntity, AirzoneBinarySensor):
    """Define an Airzone Zone binary sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneBinarySensorEntityDescription,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_name = f"{zone_data[AZD_NAME]} {description.name}"
        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description
