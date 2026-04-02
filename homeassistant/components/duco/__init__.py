"""The Duco integration."""

from __future__ import annotations

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import DucoConfigEntry, DucoCoordinator

__all__ = ["DucoConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Set up Duco from a config entry."""
    client = DucoClient(
        session=async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
    )

    try:
        board_info = await client.async_get_board_info()
    except (DucoConnectionError, DucoError) as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Duco box at {entry.data[CONF_HOST]}: {err}"
        ) from err

    coordinator = DucoCoordinator(hass, entry, client, board_info)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Unload a Duco config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
