"""Support for Honeywell Lyric binary sensors."""

from typing import override

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import LyricLeakDetectorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LyricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Honeywell Lyric binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        LyricLeakDetectorBinarySensor(coordinator, location, device)
        for location in coordinator.data.locations
        for device in location.devices
        if device.device_class == "LeakDetector" and device.device_id
    )


class LyricLeakDetectorBinarySensor(LyricLeakDetectorEntity, BinarySensorEntity):
    """Define a Honeywell Lyric leak detector binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "water_leak"

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize the leak detector binary sensor."""
        super().__init__(coordinator, location, device, "water_leak")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether water is detected."""
        return self.device.water_present
