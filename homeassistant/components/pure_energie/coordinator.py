"""Coordinator for the Pure Energie integration."""

from __future__ import annotations

from typing import NamedTuple

from gridnet import Device, GridNet, SmartBridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class PureEnergieData(NamedTuple):
    """Class for defining data in dict."""

    device: Device
    smartbridge: SmartBridge


class PureEnergieDataUpdateCoordinator(DataUpdateCoordinator[PureEnergieData]):
    """Class to manage fetching Pure Energie data from single eindpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize global Pure Energie data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.gridnet = GridNet(
            self.config_entry.data[CONF_HOST], session=async_get_clientsession(hass)
        )

    async def _async_update_data(self) -> PureEnergieData:
        """Fetch data from SmartBridge."""
        return PureEnergieData(
            device=await self.gridnet.device(),
            smartbridge=await self.gridnet.smartbridge(),
        )
