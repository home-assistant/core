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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry
from .entity import DiffuserSensorsEntity, async_add_diffusers

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
    RitualsBinarySensorEntityDescription(
        key="cartridge",
        translation_key="cartridge",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda sensors: sensors.has_cartridge,
        has_fn=lambda _: True,
        sensor=Sensor.PERFUME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser binary sensors."""
    runtime_data = config_entry.runtime_data

    @callback
    def add_diffusers(hublots: list[str]) -> None:
        async_add_entities(
            RitualsBinarySensorEntity(
                runtime_data.sensors[hublot], description, description.sensor
            )
            for hublot in hublots
            for description in ENTITY_DESCRIPTIONS
            if description.has_fn(runtime_data.hubs.data[hublot])
        )

    async_add_diffusers(config_entry, add_diffusers)


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
