"""The Duco integration."""

from __future__ import annotations

from duco import DucoClient, build_ssl_context

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import DucoConfigEntry, DucoCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Set up Duco from a config entry."""
    ssl_context = await hass.async_add_executor_job(build_ssl_context)
    client = DucoClient(
        session=async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        ssl_context=ssl_context,
    )

    coordinator = DucoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Unload a Duco config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
