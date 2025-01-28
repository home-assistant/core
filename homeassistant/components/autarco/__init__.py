"""The Autarco integration."""

from __future__ import annotations

import asyncio

from autarco import Autarco, AutarcoConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AutarcoDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type AutarcoConfigEntry = ConfigEntry[list[AutarcoDataUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: AutarcoConfigEntry) -> bool:
    """Set up Autarco from a config entry."""
    client = Autarco(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    try:
        account_sites = await client.get_account()
    except AutarcoConnectionError as err:
        await client.close()
        raise ConfigEntryNotReady from err

    coordinators: list[AutarcoDataUpdateCoordinator] = [
        AutarcoDataUpdateCoordinator(hass, client, site) for site in account_sites
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutarcoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
