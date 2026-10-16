"""Support for Rituals Perfume Genie binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from ritualsgenie import RitualsGenieHub, RitualsGenieSensors, Sensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry
from .entity import DiffuserSensorsEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RitualsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Rituals binary sensor entities."""

    is_on_fn: Callable[[RitualsGenieSensors], bool | None]
    has_fn: Callable[[RitualsGenieHub], bool]
    sensor: Sensor


ENTITY_DESCRIPTIONS = (
    RitualsBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda sensors: sensors.battery_charging,
        has_fn=lambda hub: hub.has_battery,
        sensor=Sensor.BATTERY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser binary sensors."""
    runtime_data = config_entry.runtime_data

    async_add_entities(
        RitualsBinarySensorEntity(coordinator, description, description.sensor)
        for hublot, coordinator in runtime_data.sensors.items()
        for description in ENTITY_DESCRIPTIONS
        if description.has_fn(runtime_data.hubs.data[hublot])
    )


class RitualsBinarySensorEntity(DiffuserSensorsEntity, BinarySensorEntity):
    """Defines a Rituals binary sensor entity."""

    entity_description: RitualsBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None

        return self.entity_description.is_on_fn(self.coordinator.data)
