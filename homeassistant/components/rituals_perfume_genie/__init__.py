"""The Rituals Perfume Genie integration."""
from datetime import timedelta
import logging

import aiohttp
from pyrituals import Account, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACCOUNT_HASH, COORDINATORS, DEVICES, DOMAIN, HUBLOT

PLATFORMS = ["binary_sensor", "number", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    session = async_get_clientsession(hass)
    account = Account(session=session)
    account.data = {ACCOUNT_HASH: entry.data.get(ACCOUNT_HASH)}

    try:
        account_devices = await account.get_devices()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATORS: {},
        DEVICES: {},
    }

    for device in account_devices:
        hublot = device.hub_data[HUBLOT]

        coordinator = RitualsDataUpdateCoordinator(hass, device)
        await coordinator.async_refresh()

        hass.data[DOMAIN][entry.entry_id][DEVICES][hublot] = device
        hass.data[DOMAIN][entry.entry_id][COORDINATORS][hublot] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class RitualsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Rituals Perfume Genie device data from single endpoint."""

    def __init__(self, hass: HomeAssistant, device: Diffuser) -> None:
        """Initialize global Rituals Perfume Genie data updater."""
        self._device = device
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.hub_data[HUBLOT]}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Rituals."""
        await self._device.update_data()
