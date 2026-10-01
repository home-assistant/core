"""Device tracker platform for the FMD integration."""

import logging
from typing import Any, override

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FmdConfigEntry
from .const import DOMAIN
from .coordinator import FmdCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FmdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FMD device tracker from a config entry."""
    async_add_entities([FmdDeviceTracker(entry.runtime_data)])


class FmdDeviceTracker(CoordinatorEntity[FmdCoordinator], TrackerEntity):
    """Representation of an FMD device tracker."""

    _attr_has_entity_name = True
    _attr_name = None  # Main entity of the device, uses the device name directly

    def __init__(self, coordinator: FmdCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        entry_data = coordinator.config_entry.data
        self._attr_unique_id = entry_data[CONF_ID]
        self._device_id = entry_data[CONF_ID]
        self._device_name = f"FMD {entry_data[CONF_ID]}"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="FMD-FOSS",
            model="Device Tracker",
        )

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        return self.coordinator.data.get("lat")

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        return self.coordinator.data.get("lon")

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    @override
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        bat = self.coordinator.data.get("bat")
        if bat is None:
            return None
        try:
            return int(bat)
        except TypeError, ValueError:
            return None

    @property
    @override
    def location_accuracy(self) -> float:
        """Return the GPS accuracy of the fix in meters."""
        accuracy = self.coordinator.data.get("accuracy")
        if accuracy is None:
            return 0.0
        try:
            return float(accuracy)
        except TypeError, ValueError:
            return 0.0

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {}
        if "time" in data:
            attributes["device_timestamp"] = data["time"]
        if "provider" in data:
            attributes["provider"] = data["provider"]
        if "date" in data:
            # Unix ms when the FMD client sent the fix (string avoids comma
            # formatting in the UI).
            attributes["device_timestamp_ms"] = str(data["date"])
        if "altitude" in data:
            attributes["altitude"] = data["altitude"]
            attributes["altitude_unit"] = "m"
        if "speed" in data:
            attributes["speed"] = data["speed"]
            attributes["speed_unit"] = "m/s"
        if "heading" in data:
            attributes["heading"] = data["heading"]
        return attributes
