"""Fault binary sensor for SteamVR Base Station."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamVRBaseStationConfigEntry
from .entity import SteamVRBaseStationEntity

PARALLEL_UPDATES = 0

FAULT = BinarySensorEntityDescription(
    key="fault",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamVRBaseStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fault binary sensor."""
    async_add_entities([SteamVRBaseStationFaultSensor(entry.runtime_data, FAULT)])


class SteamVRBaseStationFaultSensor(SteamVRBaseStationEntity, BinarySensorEntity):
    """On when the station reports a fault."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the station reports a fault."""
        return self.coordinator.station.state.faulty
