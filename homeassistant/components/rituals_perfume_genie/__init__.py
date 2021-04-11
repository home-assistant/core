"""The Rituals Perfume Genie integration."""
import asyncio
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientConnectorError
from pyrituals import Account

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACCOUNT_HASH, COORDINATORS, DEVICES, DOMAIN, HUB, HUBLOT

PLATFORMS = ["switch", "sensor"]

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
    except ClientConnectorError as ex:
        raise ConfigEntryNotReady from ex

    hublots = []
    devices = {}
    for device in account_devices:
        hublot = device.data[HUB][HUBLOT]
        hublots.append(hublot)
        devices[hublot] = device

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATORS: {},
        DEVICES: devices,
    }

    for hublot in hublots:
        device = hass.data[DOMAIN][entry.entry_id][DEVICES][hublot]

        async def async_update_data():
            await device.update_data()
            return device.data

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{hublot}",
            update_method=async_update_data,
            update_interval=UPDATE_INTERVAL,
        )

        await coordinator.async_refresh()

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
