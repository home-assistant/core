"""Support for the Swedish weather institute weather  base entities."""

from __future__ import annotations

import aiohttp
from pysmhi import SMHIPointForecast

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class SmhiWeatherBaseEntity(Entity):
    """Representation of a base weather entity."""

    _attr_attribution = "Swedish weather institute (SMHI)"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        latitude: str,
        longitude: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the SMHI base weather entity."""
        self._attr_unique_id = f"{latitude}, {longitude}"
        self._smhi_api = SMHIPointForecast(longitude, latitude, session=session)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{latitude}, {longitude}")},
            manufacturer="SMHI",
            model="v2",
            configuration_url="http://opendata.smhi.se/apidocs/metfcst/parameters.html",
        )
