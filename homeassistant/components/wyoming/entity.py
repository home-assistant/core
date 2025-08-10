"""Wyoming entities."""

from __future__ import annotations

from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN
from .devices import SatelliteDevice


class WyomingSatelliteEntity(entity.Entity):
    """Wyoming satellite entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: SatelliteDevice) -> None:
        """Initialize entity."""
        self._device = device
        self._attr_unique_id = f"{device.satellite_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.satellite_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
