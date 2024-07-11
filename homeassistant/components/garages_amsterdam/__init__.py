"""The Garages Amsterdam integration."""

import asyncio
from datetime import timedelta
import logging

from odp_amsterdam import ODPAmsterdam, VehicleType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garages Amsterdam from a config entry."""
    await get_coordinator(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Garages Amsterdam config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.data.pop(DOMAIN)

    return unload_ok


async def get_coordinator(
    hass: HomeAssistant,
) -> DataUpdateCoordinator:
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_garages():
        async with asyncio.timeout(10):
            return {
                garage.garage_name: garage
                for garage in await ODPAmsterdam(
                    session=aiohttp_client.async_get_clientsession(hass)
                ).all_garages(vehicle=VehicleType.CAR)
            }

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_garages,
        update_interval=timedelta(minutes=10),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = coordinator
    return coordinator
