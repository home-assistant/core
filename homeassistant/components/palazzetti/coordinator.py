"""Helpers to help coordinate updates."""

from typing import TypedDict

from pypalazzetti.client import PalazzettiClient
from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    AVAILABLE,
    DOMAIN,
    EXHAUST_TEMPERATURE,
    FAN_SPEED,
    IS_HEATING,
    LOGGER,
    OUTLET_TEMPERATURE,
    PELLET_QUANTITY,
    ROOM_TEMPERATURE,
    SCAN_INTERVAL,
    TARGET_TEMPERATURE,
)


class PalazzettiData(TypedDict):
    """Class for defining data in dict."""

    available: bool
    is_heating: bool
    target_temperature: int
    room_temperature: float
    outlet_temperature: float
    exhaust_temperature: float
    pellet_quantity: int
    fan_speed: int


class PalazzettiDataUpdateCoordinator(DataUpdateCoordinator[PalazzettiData]):
    """Class to manage fetching Palazzetti data from a Palazzetti hub."""

    entry: ConfigEntry
    palazzetti: PalazzettiClient

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize global Palazzetti data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.palazzetti = PalazzettiClient(entry.data[CONF_HOST])

    async def _async_update_data(self) -> PalazzettiData:
        """Fetch data from Palazzetti."""
        try:
            available = await self.palazzetti.update_state()
        except (CommunicationError, ValidationError) as err:
            LOGGER.warning(err)
            available = False

        data: PalazzettiData = {
            AVAILABLE: available,
            IS_HEATING: self.palazzetti.is_heating,
            TARGET_TEMPERATURE: self.palazzetti.target_temperature,
            ROOM_TEMPERATURE: self.palazzetti.room_temperature,
            OUTLET_TEMPERATURE: self.palazzetti.outlet_temperature,
            EXHAUST_TEMPERATURE: self.palazzetti.exhaust_temperature,
            PELLET_QUANTITY: self.palazzetti.pellet_quantity,
            FAN_SPEED: self.palazzetti.fan_speed,
        }
        return data
