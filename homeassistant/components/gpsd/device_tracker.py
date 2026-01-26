"""Device tracker platform for GPSD integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GPSDConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GPSDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GPSD device tracker platform."""
    async_add_entities([GpsdDeviceTracker(config_entry)])


class GpsdDeviceTracker(TrackerEntity):
    """Representation of a GPS receiver available via GPSD."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: GPSDConfigEntry,
    ) -> None:
        """Initialize the GPSD device tracker."""
        self._attr_unique_id = f"{config_entry.entry_id}-device_tracker"
        self._attr_name = config_entry.title

        self._entry = config_entry
        self.agps_thread = config_entry.runtime_data

    @property
    def should_poll(self) -> bool:
        """Enable polling of data."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        value = self.agps_thread.data_stream.lat
        return None if value == "n/a" else value

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        value = self.agps_thread.data_stream.lon
        return None if value == "n/a" else value
