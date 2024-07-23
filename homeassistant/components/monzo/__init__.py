"""The Monzo integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AuthenticatedMonzoAPI
from .const import DOMAIN
from .data import MonzoData, MonzoSensorData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monzo from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    async def async_get_monzo_api_data() -> MonzoSensorData:
        monzo_data: MonzoData = hass.data[DOMAIN][entry.entry_id]
        accounts = await external_api.user_account.accounts()
        pots = await external_api.user_account.pots()
        monzo_data.accounts = accounts
        monzo_data.pots = pots
        return MonzoSensorData(accounts=accounts, pots=pots)

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    external_api = AuthenticatedMonzoAPI(
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
    hass.data[DOMAIN][entry.entry_id] = MonzoData(external_api, coordinator)

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
