"""The Rituals Perfume Genie integration."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from pyrituals import Account, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACCOUNT_HASH, COORDINATORS, DEVICES, DOMAIN, HUB, HUBLOT

PLATFORMS = ["binary_sensor", "sensor", "switch"]

EMPTY_CREDENTIALS = ""

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Rituals Perfume Genie from a config entry."""
    session = async_get_clientsession(hass)
    account = Account(EMPTY_CREDENTIALS, EMPTY_CREDENTIALS, session)
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
        hublot = device.data[HUB][HUBLOT]

        coordinator = RitualsPerufmeGenieDataUpdateCoordinator(hass, device)
        await coordinator.async_refresh()

        hass.data[DOMAIN][entry.entry_id][DEVICES][hublot] = device
        hass.data[DOMAIN][entry.entry_id][COORDINATORS][hublot] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class RitualsPerufmeGenieDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Rituals Perufme Genie device data from single endpoint."""

    def __init__(self, hass: HomeAssistant, device: Diffuser):
        """Initialize global Rituals Perufme Genie data updater."""
        self._device = device
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.data[HUB][HUBLOT]}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Rituals."""
        await self._device.update_data()
        return self._device.data
