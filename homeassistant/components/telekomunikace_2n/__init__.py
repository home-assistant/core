"""The 2N Telekomunikace integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from py2n import Py2NConnectionData, Py2NDevice, Py2NDeviceData
from py2n.exceptions import DeviceConnectionError, InvalidAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_CONFIG_ENTRY, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERNVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 2N from a config entry."""
    session = aiohttp.ClientSession()

    try:
        device = await Py2NDevice.create(
            session,
            options=Py2NConnectionData(
                ip_address=entry.data[CONF_HOST],
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
            ),
        )
    except (DeviceConnectionError, InvalidAuthError) as err:
        raise ConfigEntryNotReady from err

    coordinator = Py2NDeviceCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY, {})
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class Py2NDeviceCoordinator(DataUpdateCoordinator[Py2NDeviceData]):
    """Class to fetch data from 2N devices."""

    def __init__(self, hass: HomeAssistant, device: Py2NDevice) -> None:
        """Initialize."""
        self.device = device

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERNVAL)

    async def _async_update_data(self) -> Py2NDeviceData:
        """Update data via library."""
        try:
            data = await self.device.update()
        except (DeviceConnectionError, InvalidAuthError) as error:
            raise UpdateFailed(error) from error
        return data
