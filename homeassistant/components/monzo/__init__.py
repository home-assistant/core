"""The Monzo integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_AUTHENTICATION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AsyncConfigEntryAuth
from .const import ACCOUNTS, CONF_COORDINATOR, DOMAIN, POTS

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monzo from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    async def async_get_monzo_api_data() -> dict[str, Any]:
        accounts = await externalapi.user_account.accounts()
        pots = await externalapi.user_account.pots()
        hass.data[DOMAIN][entry.entry_id][ACCOUNTS] = accounts
        hass.data[DOMAIN][entry.entry_id][POTS] = pots
        return {ACCOUNTS: accounts, POTS: pots}

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    externalapi = AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_monzo_api_data,
        update_interval=timedelta(minutes=1),
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_AUTHENTICATION: externalapi,
        CONF_COORDINATOR: coordinator,
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in data:
        data.pop(entry.entry_id)

    return unload_ok
