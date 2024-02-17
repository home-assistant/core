"""Summary binary data from Fyta."""
from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FytaCoordinator, FytaEntity

BINARY_SENSORS: Final[list[BinarySensorEntityDescription]] = [
    BinarySensorEntityDescription(
        key="online",
        translation_key="fyta_online",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="battery_status",
        translation_key="fyta_battery_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud binary sensors."""
    coordinator: FytaCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FytaBinarySensor(coordinator, entry, sensor)
            for sensor in BINARY_SENSORS
            if sensor.key in coordinator.data
        ]
    )

    for plant_id in coordinator.plant_list:
        async_add_entities(
            [
                FytaBinarySensor(coordinator, entry, sensor, plant_id)
                for sensor in BINARY_SENSORS
                if sensor.key in coordinator.data[plant_id]
            ]
        )


class FytaBinarySensor(FytaEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        val = self.coordinator.data.get(self.entity_description.key)
        return val is True or val == "yes"
