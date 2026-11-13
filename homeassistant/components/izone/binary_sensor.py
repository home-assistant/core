"""Support for iZone binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import override

from pizone import Zone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .entity import IZoneCoordinatorEntity, zone_device_info

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IZoneBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an iZone zone binary sensor."""

    is_on_fn: Callable[[Zone], bool | None]
    exists_fn: Callable[[Zone], bool]


ZONE_BINARY_SENSOR_DESCRIPTIONS: tuple[IZoneBinarySensorEntityDescription, ...] = (
    IZoneBinarySensorEntityDescription(
        key="damper_fault",
        translation_key="damper_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=attrgetter("damper_fault"),
        exists_fn=lambda zone: zone.damper_fault is not None,
    ),
    IZoneBinarySensorEntityDescription(
        key="sensor_fault",
        translation_key="sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=attrgetter("sensor_fault"),
        exists_fn=lambda zone: (
            zone.sensor_fault is not None
            and zone.sensor_type is not Zone.SensorType.NONE
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iZone binary sensor entities from the entry coordinator."""
    coordinator = entry.runtime_data
    async_add_entities(
        IZoneZoneBinarySensor(coordinator, description, zone)
        for zone in coordinator.controller.zones
        for description in ZONE_BINARY_SENSOR_DESCRIPTIONS
        if description.exists_fn(zone)
    )


class IZoneZoneBinarySensor(IZoneCoordinatorEntity, BinarySensorEntity):
    """Binary sensor backed by a pizone Zone."""

    _attr_has_entity_name = True
    entity_description: IZoneBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        description: IZoneBinarySensorEntityDescription,
        zone: Zone,
    ) -> None:
        """Initialize the binary sensor for *zone*."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone = zone
        self._attr_unique_id = (
            f"{coordinator.controller.device_uid}_z{zone.index + 1}_{description.key}"
        )
        self._attr_device_info = zone_device_info(coordinator, zone)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the zone reports the fault."""
        return self.entity_description.is_on_fn(self._zone)
