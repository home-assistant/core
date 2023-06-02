"""The OpenTherm Web integration."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, HOST, LOGGER, SCAN_INTERVAL, SECRET
from .opentherm_webapi import OpenThermWebApi

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenTherm Web from a config entry."""

    opentherm = OpenThermWebApi(entry.data[HOST], entry.data[SECRET])
    auth_valid = await opentherm.authenticate()

    if not auth_valid:
        LOGGER.error("Invalid authentication")
        return False

    coordinator = OpenThermWebCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OpenThermWebData(TypedDict):
    """Class for defining data in dict."""


class OpenThermWebCoordinator(DataUpdateCoordinator[OpenThermWebData]):
    """Class to manage fetching OpenThermWeb data from single endpoint."""

    webapi: OpenThermWebApi

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global OpenThermWeb data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.webapi = OpenThermWebApi(entry.data[HOST], entry.data[SECRET])

    async def _async_update_data(self) -> OpenThermWebData:
        """Fetch data from OpenThermWeb."""
        data: OpenThermWebData = {}
        return data
