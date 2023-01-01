"""The P1 Monitor integration."""
from __future__ import annotations

from typing import TypedDict

from p1monitor import (
    P1Monitor,
    P1MonitorConnectionError,
    P1MonitorNoDataError,
    Phases,
    Settings,
    SmartMeter,
    WaterMeter,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
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
    SERVICE_WATERMETER,
)

PLATFORMS = [Platform.SENSOR]


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload P1 Monitor config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


class P1MonitorData(TypedDict):
    """Class for defining data in dict."""

    smartmeter: SmartMeter
    phases: Phases
    settings: Settings
    watermeter: WaterMeter | None


class P1MonitorDataUpdateCoordinator(DataUpdateCoordinator[P1MonitorData]):
    """Class to manage fetching P1 Monitor data from single endpoint."""

    config_entry: ConfigEntry
    has_water_meter: bool | None = None

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
            SERVICE_WATERMETER: None,
        }

        if self.has_water_meter or self.has_water_meter is None:
            try:
                data[SERVICE_WATERMETER] = await self.p1monitor.watermeter()
                self.has_water_meter = True
            except (P1MonitorNoDataError, P1MonitorConnectionError):
                LOGGER.debug("No water meter data received from P1 Monitor")
                if self.has_water_meter is None:
                    self.has_water_meter = False

        return data
