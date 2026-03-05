"""
Platform for GPS device tracker integration.
Reads position data from PajGpsCoordinator and exposes it as a TrackerEntity.
"""
from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PajGpsCoordinator
from .__init__ import PajGpsConfigEntry
import logging

_LOGGER = logging.getLogger(__name__)

class PajGPSPositionSensor(CoordinatorEntity[PajGpsCoordinator], TrackerEntity):
    """Tracker entity that reads position from the coordinator snapshot."""

    _attr_has_entity_name = True
    _attr_name = None  # Primary feature of the device — entity name equals device name
    _attr_icon = "mdi:map-marker"

    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_gps"

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)

    @property
    def latitude(self) -> float | None:
        tp = self.coordinator.data.positions.get(self._device_id)
        return float(tp.lat) if tp and tp.lat is not None else None

    @property
    def longitude(self) -> float | None:
        tp = self.coordinator.data.positions.get(self._device_id)
        return float(tp.lng) if tp and tp.lng is not None else None

    @property
    def source_type(self) -> str:
        return "gps"

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        elevation = self.coordinator.data.elevations.get(self._device_id)
        if elevation is not None:
            attrs["elevation"] = elevation
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities,
) -> None:
    """Set up PAJ GPS tracker entities from a config entry."""
    coordinator: PajGpsCoordinator = config_entry.runtime_data

    entities = [
        PajGPSPositionSensor(coordinator, device.id)
        for device in coordinator.data.devices
        if device.id is not None
    ]

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No PAJ GPS devices found to add as trackers")