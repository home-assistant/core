"""The Pure Energie integration."""
from __future__ import annotations

from typing import NamedTuple

from gridnet import Device, GridNet, SmartBridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pure Energie from a config entry."""

    coordinator = PureEnergieDataUpdateCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.gridnet.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pure Energie config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


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
