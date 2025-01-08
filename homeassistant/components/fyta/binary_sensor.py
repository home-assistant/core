"""Binary sensors for Fyta."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from fyta_cli.fyta_models import Plant

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FytaConfigEntry
from .entity import FytaPlantEntity


@dataclass(frozen=True, kw_only=True)
class FytaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Fyta binary sensor entity."""

    value_fn: Callable[[Plant], bool]


BINARY_SENSORS: Final[list[FytaBinarySensorEntityDescription]] = [
    FytaBinarySensorEntityDescription(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.low_battery,
    ),
    FytaBinarySensorEntityDescription(
        key="notification_light",
        translation_key="notification_light",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda plant: plant.notification_light,
    ),
    FytaBinarySensorEntityDescription(
        key="notification_nutrition",
        translation_key="notification_nutrition",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda plant: plant.notification_nutrition,
    ),
    FytaBinarySensorEntityDescription(
        key="notification_temperature",
        translation_key="notification_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda plant: plant.notification_temperature,
    ),
    FytaBinarySensorEntityDescription(
        key="notification_water",
        translation_key="notification_water",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda plant: plant.notification_water,
    ),
    FytaBinarySensorEntityDescription(
        key="sensor_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.sensor_update_available,
    ),
    FytaBinarySensorEntityDescription(
        key="productive_plant",
        translation_key="productive_plant",
        value_fn=lambda plant: plant.productive_plant,
    ),
    FytaBinarySensorEntityDescription(
        key="repotted",
        translation_key="repotted",
        value_fn=lambda plant: plant.repotted,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: FytaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FYTA binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        FytaPlantBinarySensor(coordinator, entry, sensor, plant_id)
        for plant_id in coordinator.fyta.plant_list
        for sensor in BINARY_SENSORS
        if sensor.key in dir(coordinator.data.get(plant_id))
    )

    def _async_add_new_device(plant_id: int) -> None:
        async_add_entities(
            FytaPlantBinarySensor(coordinator, entry, sensor, plant_id)
            for sensor in BINARY_SENSORS
            if sensor.key in dir(coordinator.data.get(plant_id))
        )

    coordinator.new_device_callbacks.append(_async_add_new_device)


class FytaPlantBinarySensor(FytaPlantEntity, BinarySensorEntity):
    """Represents a Fyta binary sensor."""

    entity_description: FytaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return value of the binary sensor."""

        return self.entity_description.value_fn(self.plant)
