"""iAlarm integration."""

from __future__ import annotations

import asyncio
import logging

from pyialarm import IAlarm

from homeassistant.components.alarm_control_panel import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, IALARM_TO_HASS

PLATFORMS = [Platform.ALARM_CONTROL_PANEL]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iAlarm config."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    ialarm = IAlarm(host, port)

    try:
        async with asyncio.timeout(10):
            mac = await hass.async_add_executor_job(ialarm.get_mac)
    except (TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = IAlarmDataUpdateCoordinator(hass, ialarm, mac)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload iAlarm config."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class IAlarmDataUpdateCoordinator(DataUpdateCoordinator[None]):  # pylint: disable=hass-enforce-coordinator-module
    """Class to manage fetching iAlarm data."""

    def __init__(self, hass: HomeAssistant, ialarm: IAlarm, mac: str) -> None:
        """Initialize global iAlarm data updater."""
        self.ialarm = ialarm
        self.state: str | None = None
        self.host: str = ialarm.host
        self.mac = mac

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> None:
        """Fetch data from iAlarm via sync functions."""
        status = self.ialarm.get_status()
        _LOGGER.debug("iAlarm status: %s", status)

        self.state = IALARM_TO_HASS.get(status)

    async def _async_update_data(self) -> None:
        """Fetch data from iAlarm."""
        try:
            async with asyncio.timeout(10):
                await self.hass.async_add_executor_job(self._update_data)
        except ConnectionError as error:
            raise UpdateFailed(error) from error
