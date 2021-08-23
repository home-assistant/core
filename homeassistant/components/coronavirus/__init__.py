"""The Coronavirus integration."""
from datetime import timedelta
import logging

import async_timeout
import coronavirus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, entity_registry, update_coordinator
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Coronavirus component."""
    # Make sure coordinator is initialized.
    await get_coordinator(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Coronavirus from a config entry."""
    if isinstance(entry.data["country"], int):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "country": entry.title}
        )

        @callback
        def _async_migrator(entity_entry: entity_registry.RegistryEntry):
            """Migrate away from unstable ID."""
            country, info_type = entity_entry.unique_id.rsplit("-", 1)
            if not country.isnumeric():
                return None
            return {"new_unique_id": f"{entry.title}-{info_type}"}

        await entity_registry.async_migrate_entries(
            hass, entry.entry_id, _async_migrator
        )

    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=entry.data["country"])

    coordinator = await get_coordinator(hass)
    if not coordinator.last_update_success:
        await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def get_coordinator(
    hass: HomeAssistant,
) -> update_coordinator.DataUpdateCoordinator:
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_cases():
        with async_timeout.timeout(10):
            return {
                case.country: case
                for case in await coronavirus.get_cases(
                    aiohttp_client.async_get_clientsession(hass)
                )
            }

    hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_cases,
        update_interval=timedelta(hours=1),
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]
