"""EPS integration."""
from __future__ import annotations

import asyncio

# from homeassistant.components.alarm_control_panel import SCAN_INTERVAL
from datetime import timedelta
import logging

from pyepsalarm import EPS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, EPS_TO_HASS

PLATFORMS = [Platform.ALARM_CONTROL_PANEL]
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EPS config."""
    token: str = entry.data[CONF_TOKEN]
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    eps_api = EPS(token, username, password)

    # Use the EPS siteId as a unique_id
    try:
        async with asyncio.timeout(10):
            site = await hass.async_add_executor_job(eps_api.get_site)
    except (asyncio.TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = EPSDataUpdateCoordinator(hass, eps_api, site)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EPS config."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class EPSDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching EPS data."""

    def __init__(self, hass: HomeAssistant, eps_api: EPS, site: str) -> None:
        """Initialize global EPS data updater."""
        self.eps_api = eps_api
        self.state: str | None = None
        self.site = site
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> None:
        """Fetch data from EPS via sync functions."""
        status = self.eps_api.get_status()
        _LOGGER.debug("EPS status: %s", status)
        self.state = EPS_TO_HASS.get(status, status)

    async def _async_update_data(self) -> None:
        """Fetch data from EPS."""
        try:
            async with asyncio.timeout(10):
                await self.hass.async_add_executor_job(self._update_data)
        except ConnectionError as error:
            raise UpdateFailed(error) from error
