"""iAlarmXR integration."""
import asyncio
import logging
from typing import Optional

from async_timeout import timeout
from pyialarmxr import IAlarmXR

from homeassistant.components.alarm_control_panel import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, IALARMXR_TO_HASS

PLATFORMS = [Platform.ALARM_CONTROL_PANEL]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iAlarmXR config."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    ialarm = IAlarmXR(host, username, password, port)

    try:
        async with timeout(10):
            mac = await hass.async_add_executor_job(ialarm.get_mac)
    except (asyncio.TimeoutError, ConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = IAlarmXRDataUpdateCoordinator(hass, ialarm, mac)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload iAlarmXR config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class IAlarmXRDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching iAlarmXR data."""

    def __init__(self, hass: HomeAssistant, ialarm: IAlarmXR, mac: str) -> None:
        """Initialize global iAlarm data updater."""
        self.ialarm = ialarm
        self.state = Optional[str]
        self.host = ialarm.host
        self.mac = mac

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> None:
        """Fetch data from iAlarmXR via sync functions."""
        status = self.ialarm.get_status()
        _LOGGER.debug("iAlarmXR status: %s", status)

        self.state = IALARMXR_TO_HASS.get(status)

    async def _async_update_data(self) -> None:
        """Fetch data from iAlarmXR."""
        try:
            async with timeout(10):
                await self.hass.async_add_executor_job(self._update_data)
        except ConnectionError as error:
            raise UpdateFailed(error) from error
