"""The PoolSense integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import poolsense

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, entity_registry, update_coordinator

from .const import DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PoolSense component."""
    # Make sure coordinator is initialized.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up PoolSense from a config entry."""
    if isinstance(entry.data["email"], str):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "email": entry.title}
        )

        @callback
        def _async_migrator(entity_entry: entity_registry.RegistryEntry):
            """Migrate away from unstable ID."""
            email, info_type = entity_entry.unique_id.rsplit("-", 1)
            if len(email) > 0:
                return None
            else:
                return {"new_unique_id": f"{entry.title}-{info_type}"}

        await entity_registry.async_migrate_entries(
            hass, entry.entry_id, _async_migrator
        )

    await get_coordinator(hass, entry)

    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=entry.data["email"])

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    return unload_ok


async def get_coordinator(hass, entry):
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_cases():
        _LOGGER.info("Run query to server")
        with async_timeout.timeout(10):
            return await poolsense.get_poolsense_data(
                aiohttp_client.async_get_clientsession(hass), entry
            )

    hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_cases,
        update_interval=timedelta(hours=1),
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]
