"""The P1 Monitor integration."""
from __future__ import annotations

from typing import TypedDict

from p1monitor import P1Monitor, Phases, Settings, SmartMeter

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
)

PLATFORMS = (SENSOR_DOMAIN,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up P1 Monitor from a config entry."""

    coordinator = P1MonitorDataUpdateCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.p1monitor.close()
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload P1 Monitor config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.p1monitor.close()
    return unload_ok


class P1MonitorData(TypedDict):
    """Class for defining data in dict."""

    smartmeter: SmartMeter
    phases: Phases
    settings: Settings


class P1MonitorDataUpdateCoordinator(DataUpdateCoordinator[P1MonitorData]):
    """Class to manage fetching P1 Monitor data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize global P1 Monitor data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.p1monitor = P1Monitor(
            self.config_entry.data[CONF_HOST], session=async_get_clientsession(hass)
        )

    async def _async_update_data(self) -> P1MonitorData:
        """Fetch data from P1 Monitor."""
        data: P1MonitorData = {
            SERVICE_SMARTMETER: await self.p1monitor.smartmeter(),
            SERVICE_PHASES: await self.p1monitor.phases(),
            SERVICE_SETTINGS: await self.p1monitor.settings(),
        }

        return data
