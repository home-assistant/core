"""Support for SleepIQ binary sensors."""
from typing import Dict

from sleepyq import Bed

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DATA_SLEEPIQ, SleepIQBedSideEntity
from .const import IS_IN_BED, SIDES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed binary sensors."""
    coordinator = hass.data[DATA_SLEEPIQ].coordinators[config_entry.data[CONF_USERNAME]]
    entities = []

    for bed_id in coordinator.data:
        for side in SIDES:
            if getattr(coordinator.data[bed_id], side) is not None:
                entities.append(IsInBedBinarySensor(coordinator, bed_id, side))

    async_add_entities(entities, True)


class IsInBedBinarySensor(SleepIQBedSideEntity, BinarySensorEntity):
    """Representation of a bed side sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Dict[str, Bed]],
        bed_id: str,
        side: str,
    ) -> None:
        """Initialize the SleepIQ bed side binary sensor."""
        super().__init__(coordinator, bed_id, side)
        self._name = IS_IN_BED
