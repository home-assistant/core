"""Support for the Airzone sensors."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from aioairzone.const import (
    AZD_AIR_DEMAND,
    AZD_ERRORS,
    AZD_FLOOR_DEMAND,
    AZD_NAME,
    AZD_PROBLEMS,
    AZD_ZONES,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_RUNNING,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneEntity
from .const import DOMAIN
from .coordinator import AirzoneUpdateCoordinator


@dataclass
class AirzoneBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes airzone binary sensor entities."""

    attributes: dict[str, str] | None = None


BINARY_SENSOR_TYPES: Final[tuple[AirzoneBinarySensorEntityDescription, ...]] = (
    AirzoneBinarySensorEntityDescription(
        device_class=DEVICE_CLASS_RUNNING,
        key=AZD_AIR_DEMAND,
        name="Air Demand",
    ),
    AirzoneBinarySensorEntityDescription(
        device_class=DEVICE_CLASS_RUNNING,
        key=AZD_FLOOR_DEMAND,
        name="Floor Demand",
    ),
    AirzoneBinarySensorEntityDescription(
        attributes={
            "errors": AZD_ERRORS,
        },
        device_class=DEVICE_CLASS_PROBLEM,
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

    binary_sensors = []
    for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        for description in BINARY_SENSOR_TYPES:
            if description.key in zone_data:
                binary_sensors.append(
                    AirzoneBinarySensor(
                        coordinator,
                        description,
                        entry,
                        system_zone_id,
                        zone_data,
                    )
                )

    async_add_entities(binary_sensors)


class AirzoneBinarySensor(AirzoneEntity, BinarySensorEntity):
    """Define an Airzone sensor."""

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
        self._attr_unique_id = f"{entry.entry_id}_{system_zone_id}_{description.key}"
        self.attributes = description.attributes
        self.entity_description = description

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return state attributes."""
        if not self.attributes:
            return None
        return {key: self.get_zone_value(val) for key, val in self.attributes.items()}

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.get_zone_value(self.entity_description.key)
