"""Base Entity for IPMA."""

from __future__ import annotations

from pyipma.api import IPMA_API
from pyipma.location import Location

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class IPMADevice(Entity):
    """Common IPMA Device Information."""

    _attr_has_entity_name = True

    def __init__(self, api: IPMA_API, location: Location) -> None:
        """Initialize device information."""
        self._api = api
        self._location = location
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{location.station_latitude}, {location.station_longitude}",
                )
            },
            manufacturer=DOMAIN,
            name=location.name,
        )
