"""Support for the Airzone sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aioairzone.const import (
    AZD_AIR_DEMAND,
    AZD_BATTERY_LOW,
    AZD_ERRORS,
    AZD_FLOOR_DEMAND,
    AZD_PROBLEMS,
    AZD_SYSTEMS,
    AZD_ZONES,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneConfigEntry
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneSystemEntity, AirzoneZoneEntity


@dataclass(frozen=True)
class AirzoneBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes airzone binary sensor entities."""

    attributes: dict[str, str] | None = None


SYSTEM_BINARY_SENSOR_TYPES: Final[tuple[AirzoneBinarySensorEntityDescription, ...]] = (
    AirzoneBinarySensorEntityDescription(
        attributes={
            "errors": AZD_ERRORS,
        },
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=AZD_PROBLEMS,
    ),
)

ZONE_BINARY_SENSOR_TYPES: Final[tuple[AirzoneBinarySensorEntityDescription, ...]] = (
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        key=AZD_AIR_DEMAND,
        translation_key="air_demand",
    ),
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.BATTERY,
        key=AZD_BATTERY_LOW,
    ),
    AirzoneBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        key=AZD_FLOOR_DEMAND,
        translation_key="floor_demand",
    ),
    AirzoneBinarySensorEntityDescription(
        attributes={
            "errors": AZD_ERRORS,
        },
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=AZD_PROBLEMS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone binary sensors from a config_entry."""
    coordinator = entry.runtime_data

    binary_sensors: list[AirzoneBinarySensor] = [
        AirzoneSystemBinarySensor(
            coordinator,
            description,
            entry,
            system_id,
            system_data,
        )
        for system_id, system_data in coordinator.data[AZD_SYSTEMS].items()
        for description in SYSTEM_BINARY_SENSOR_TYPES
        if description.key in system_data
    ]

    binary_sensors.extend(
        AirzoneZoneBinarySensor(
            coordinator,
            description,
            entry,
            system_zone_id,
            zone_data,
        )
        for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items()
        for description in ZONE_BINARY_SENSOR_TYPES
        if description.key in zone_data
    )

    async_add_entities(binary_sensors)


class AirzoneBinarySensor(AirzoneEntity, BinarySensorEntity):
    """Define an Airzone binary sensor."""

    entity_description: AirzoneBinarySensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update binary sensor attributes."""
        self._attr_is_on = self.get_airzone_value(self.entity_description.key)
        if self.entity_description.attributes:
            self._attr_extra_state_attributes = {
                key: self.get_airzone_value(val)
                for key, val in self.entity_description.attributes.items()
            }


class AirzoneSystemBinarySensor(AirzoneSystemEntity, AirzoneBinarySensor):
    """Define an Airzone System binary sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: AirzoneBinarySensorEntityDescription,
        entry: ConfigEntry,
        system_id: str,
        system_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_data)
        self._attr_unique_id = f"{self._attr_unique_id}_{system_id}_{description.key}"
        self.entity_description = description
        self._async_update_attrs()


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

        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description
        self._async_update_attrs()
