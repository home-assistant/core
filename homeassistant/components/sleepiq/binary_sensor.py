"""Support for SleepIQ sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR
from .device import SleepNumberCoordinatorEntity

ICON = "mdi:bed"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ binary sensor."""

    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]
    status_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]

    entities: list[IsInBedBinarySensor] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(IsInBedBinarySensor(sleeper, bed, status_coordinator))

    async_add_entities(entities)


class IsInBedBinarySensor(SleepNumberCoordinatorEntity, BinarySensorEntity):
    """Implementation of a SleepIQ presence sensor."""

    def __init__(self, sleeper, bed, status_coordinator):
        """Initialize the sensor."""
        super().__init__(bed, status_coordinator)
        self._sleeper = sleeper
        self._attr_name = f"SleepNumber {bed.name} {sleeper.name} Is In Bed"
        self._attr_unique_id = f"{bed.id}-{sleeper.side}-InBed"
        self._attr_icon = ICON
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._sleeper.in_bed
