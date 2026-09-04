"""The Discogs integration."""

from functools import partial

import discogs_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

from .const import PLATFORMS

type DiscogsConfigEntry = ConfigEntry[discogs_client.Client]


async def async_setup_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Set up Discogs from a config entry."""
    try:
        client = await hass.async_add_executor_job(
            partial(
                discogs_client.Client,
                SERVER_SOFTWARE,
                user_token=entry.data[CONF_TOKEN],
            )
        )
        await hass.async_add_executor_job(client.identity)
    except discogs_client.exceptions.HTTPError as err:
        raise ConfigEntryNotReady(f"Error communicating with Discogs: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Unload Discogs config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
