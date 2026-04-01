"""Device tracker platform for NRGkick."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NRGkickConfigEntry, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity, get_nested_dict_value

PARALLEL_UPDATES = 0

TRACKER_KEY: Final = "gps_tracker"


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick device tracker based on a config entry."""
    coordinator = entry.runtime_data

    data = coordinator.data
    assert data is not None

    info_data: dict[str, Any] = data.info
    general_info: dict[str, Any] = info_data.get("general", {})
    model_type = general_info.get("model_type")

    # GPS module is only available on SIM-capable models (same check as cellular
    # sensors). SIM-capable models include "SIM" in their model type string.
    has_sim_module = isinstance(model_type, str) and "SIM" in model_type.upper()

    if has_sim_module:
        async_add_entities([NRGkickDeviceTracker(coordinator)])


class NRGkickDeviceTracker(NRGkickEntity, TrackerEntity):
    """Representation of a NRGkick GPS device tracker."""

    _attr_translation_key = TRACKER_KEY
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, TRACKER_KEY)

    def _gps_float(self, key: str) -> float | None:
        """Return a GPS value as float, or None if GPS data is unavailable."""
        value = get_nested_dict_value(self.coordinator.data.info, "gps", key)
        return float(value) if value is not None else None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._gps_float("latitude")

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._gps_float("longitude")

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device."""
        return self._gps_float("accuracy") or 0.0
