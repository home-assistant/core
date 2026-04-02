"""Support for OVO Energy."""

from __future__ import annotations

import logging

import aiohttp
from ovoenergy import OVOEnergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ACCOUNT, DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import OVOEnergyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy from a config entry."""

    client = OVOEnergy(
        client_session=async_get_clientsession(hass),
    )

    if (custom_account := entry.data.get(CONF_ACCOUNT)) is not None:
        client.custom_account_id = custom_account

    try:
        if not await client.authenticate(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        ):
            raise ConfigEntryAuthFailed

        await client.bootstrap_accounts()
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise ConfigEntryNotReady from exception

    coordinator = OVOEnergyDataUpdateCoordinator(hass, entry, client)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Setup components
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OVO Energy config entry."""
    # Unload sensors
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
