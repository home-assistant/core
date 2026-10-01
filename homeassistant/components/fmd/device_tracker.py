"""Device tracker platform for the FMD integration."""

import logging
from typing import Any, override

from fmd_api.models import Location

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.const import CONF_ID, CONF_URL
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
        # Server-scoped identity (same as the config-entry unique_id) so the
        # same account ID on two different servers does not collide.
        scope = f"{entry_data[CONF_URL]}/{entry_data[CONF_ID]}"
        self._attr_unique_id = scope
        self._device_id = scope
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
        return self.coordinator.data.lat

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        return self.coordinator.data.lon

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    @override
    def location_accuracy(self) -> float:
        """Return the GPS accuracy of the fix in meters."""
        return self.coordinator.data.accuracy_m or 0.0

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        data: Location = self.coordinator.data
        attributes: dict[str, Any] = {}
        if data.timestamp is not None:
            attributes["device_timestamp"] = data.timestamp.isoformat()
        if data.provider is not None:
            attributes["provider"] = data.provider
        if data.timestamp_ms is not None:
            # Unix ms when the FMD client sent the fix (string avoids comma
            # formatting in the UI).
            attributes["device_timestamp_ms"] = str(data.timestamp_ms)
        if data.altitude_m is not None:
            attributes["altitude"] = data.altitude_m
            attributes["altitude_unit"] = "m"
        if data.speed_m_s is not None:
            attributes["speed"] = data.speed_m_s
            attributes["speed_unit"] = "m/s"
        if data.heading_deg is not None:
            attributes["heading"] = data.heading_deg
        if data.battery_pct is not None:
            # Battery is reported by the device alongside the location fix.
            # The deprecated tracker battery_level property is not used; a
            # dedicated battery sensor is planned as a follow-up platform.
            attributes["battery"] = data.battery_pct
        return attributes
