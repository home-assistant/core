"""Base Entity for IPMA."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class IPMADevice(Entity):
    """Common IPMA Device Information."""

    def __init__(self, location) -> None:
        """Initialize device information."""
        self._location = location
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{self._location.station_latitude}, {self._location.station_longitude}",
                )
            },
            manufacturer=DOMAIN,
            name=self._location.name,
        )
