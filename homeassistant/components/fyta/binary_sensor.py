"""Binary sensors for Fyta."""

from __future__ import annotations

from typing import Final

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

BINARY_SENSORS: Final[list[BinarySensorEntityDescription]] = [
    BinarySensorEntityDescription(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="notification_light",
        translation_key="notification_light",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="notification_nutrition",
        translation_key="notification_nutrition",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="notification_temperature",
        translation_key="notification_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="notification_water",
        translation_key="notification_water",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="sensor_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="productive_plant",
        translation_key="productive_plant",
    ),
    BinarySensorEntityDescription(
        key="repotted",
        translation_key="repotted",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: FytaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FYTA binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FytaPlantBinarySensor(coordinator, entry, sensor, plant_id)
            for plant_id in coordinator.fyta.plant_list
            for sensor in BINARY_SENSORS
            if sensor.key in dir(coordinator.data.get(plant_id))
        ]
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

    entity_description: BinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return value of the binary sensor."""

        return bool(getattr(self.plant, self.entity_description.key))
