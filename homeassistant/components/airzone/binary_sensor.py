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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirzoneConfigEntry, AirzoneUpdateCoordinator
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Airzone binary sensors from a config_entry."""
    coordinator = entry.runtime_data

    added_systems: set[str] = set()
    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of binary sensors."""

        entities: list[AirzoneBinarySensor] = []

        systems_data = coordinator.data.get(AZD_SYSTEMS, {})
        received_systems = set(systems_data)
        new_systems = received_systems - added_systems
        if new_systems:
            entities.extend(
                AirzoneSystemBinarySensor(
                    coordinator,
                    description,
                    entry,
                    system_id,
                    systems_data.get(system_id),
                )
                for system_id in new_systems
                for description in SYSTEM_BINARY_SENSOR_TYPES
                if description.key in systems_data.get(system_id)
            )
            added_systems.update(new_systems)

        zones_data = coordinator.data.get(AZD_ZONES, {})
        received_zones = set(zones_data)
        new_zones = received_zones - added_zones
        if new_zones:
            entities.extend(
                AirzoneZoneBinarySensor(
                    coordinator,
                    description,
                    entry,
                    system_zone_id,
                    zones_data.get(system_zone_id),
                )
                for system_zone_id in new_zones
                for description in ZONE_BINARY_SENSOR_TYPES
                if description.key in zones_data.get(system_zone_id)
            )
            added_zones.update(new_zones)

        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


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
