"""Helpers to help coordinate updates."""

from typing import TypedDict

from palazzetti_sdk_local_api import Hub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    API_EXHAUST_TEMPERATURE,
    API_FAN_MODE,
    API_MODE,
    API_OUTPUT_TEMPERATURE,
    API_PELLET_QUANTITY,
    API_ROOM_TEMPERATURE,
    API_TARGET_TEMPERATURE,
    DOMAIN,
    EXHAUST_TEMPERATURE,
    FAN_MODE,
    HOST,
    LOGGER,
    MODE,
    OUTPUT_TEMPERATURE,
    PELLET_QUANTITY,
    ROOM_TEMPERATURE,
    SCAN_INTERVAL,
    TARGET_TEMPERATURE,
)


class PalazzettiData(TypedDict):
    """Class for defining data in dict."""

    mode: int
    target_temperature: int
    room_temperature: float
    output_temperature: float
    exhaust_temperature: float
    pellet_quantity: int
    fan_mode: int


class PalazzettiDataUpdateCoordinator(DataUpdateCoordinator[PalazzettiData]):
    """Class to manage fetching Palazzetti data from a Palazzetti hub."""

    entry: ConfigEntry
    hub: Hub

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize global Palazzetti data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.hub = Hub(host=entry.data[HOST], isbiocc=False)

    async def _async_update_data(self) -> PalazzettiData:
        """Fetch data from Palazzetti."""
        await self.hub.async_update(discovery=True, deep=True)
        api_data = self.hub.product.get_attributes()
        data: PalazzettiData = {
            MODE: api_data[API_MODE],
            TARGET_TEMPERATURE: api_data[API_TARGET_TEMPERATURE],
            ROOM_TEMPERATURE: api_data[API_ROOM_TEMPERATURE],
            OUTPUT_TEMPERATURE: api_data[API_OUTPUT_TEMPERATURE],
            EXHAUST_TEMPERATURE: api_data[API_EXHAUST_TEMPERATURE],
            PELLET_QUANTITY: api_data[API_PELLET_QUANTITY],
            FAN_MODE: api_data[API_FAN_MODE],
        }
        return data
