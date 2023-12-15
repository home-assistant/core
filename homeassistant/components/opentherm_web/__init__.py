"""The OpenTherm Web integration."""
from __future__ import annotations

from typing import NamedTuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, HOST, LOGGER, SCAN_INTERVAL, SECRET
from .opentherm_web_api import OpenThermWebApi

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.WATER_HEATER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenTherm Web from a config entry."""

    coordinator = OpenThermWebCoordinator(hass, entry)
    try:
        auth_valid = await hass.async_add_executor_job(coordinator.web_api.authenticate)
    except Exception as ex:
        raise ConfigEntryNotReady("Authentication failed") from ex

    if not auth_valid:
        LOGGER.error("Invalid authentication")
        return False

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


class OpenThermWebData(NamedTuple):
    """Class for defining data in dict."""

    web_api: OpenThermWebApi


class OpenThermWebCoordinator(DataUpdateCoordinator[OpenThermWebData]):
    """Class to manage fetching OpenThermWeb data from single endpoint."""

    web_api: OpenThermWebApi

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

        self.web_api = OpenThermWebApi(entry.data[HOST], entry.data[SECRET])

    async def _async_update_data(self) -> OpenThermWebData:
        """Fetch data from OpenThermWeb."""
        await self.hass.async_add_executor_job(self.web_api.refresh_controller)
        return OpenThermWebData(web_api=self.web_api)
