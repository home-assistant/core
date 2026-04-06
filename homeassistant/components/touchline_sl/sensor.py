"""Roth Touchline SL sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pytouchlinesl import Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TouchlineSLConfigEntry, TouchlineSLModuleCoordinator
from .entity import TouchlineSLZoneEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TouchlineSLSensorEntityDescription(SensorEntityDescription):
    """Describes a Touchline SL sensor entity."""

    value_fn: Callable[[Zone], int | None]
    exists_fn: Callable[[Zone], bool] = lambda _: True


SENSORS: tuple[TouchlineSLSensorEntityDescription, ...] = (
    TouchlineSLSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda zone: zone.battery_level,
        exists_fn=lambda zone: zone.battery_level is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineSLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Touchline SL sensors."""
    coordinators = entry.runtime_data
    async_add_entities(
        TouchlineSLSensor(
            coordinator=coordinator, zone_id=zone_id, description=description
        )
        for coordinator in coordinators
        for zone_id in coordinator.data.zones
        for description in SENSORS
        if description.exists_fn(coordinator.data.zones[zone_id])
    )


class TouchlineSLSensor(TouchlineSLZoneEntity, SensorEntity):
    """A sensor entity for a Roth Touchline SL zone."""

    entity_description: TouchlineSLSensorEntityDescription

    def __init__(
        self,
        coordinator: TouchlineSLModuleCoordinator,
        zone_id: int,
        description: TouchlineSLSensorEntityDescription,
    ) -> None:
        """Initialise a Touchline SL sensor."""
        super().__init__(coordinator, zone_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"module-{coordinator.data.module.id}-zone-{zone_id}-{description.key}"
        )

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.zone)
