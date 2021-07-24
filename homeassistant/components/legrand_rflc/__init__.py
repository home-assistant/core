"""The Legrand RFLC integration.

https://www.legrand.us/solutions/smart-lighting/radio-frequency-lighting-controls
"""

import asyncio
from collections.abc import Mapping
from typing import Final

import lc7001.aio

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_AUTHENTICATION, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: Final = ["light"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Legrand RFLC integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up Legrand LC7001 from a config entry."""
    entry_id = entry.entry_id
    data = entry.data
    host = data[CONF_HOST]
    kwargs = {}
    if CONF_AUTHENTICATION in data:
        kwargs["key"] = bytes.fromhex(data[CONF_AUTHENTICATION])
    if CONF_PORT in data:  # for testing only (server emulation on localhost)
        kwargs["port"] = data[CONF_PORT]
    hass.data[DOMAIN][entry_id] = hub = lc7001.aio.Hub(host, **kwargs)

    async def setup_platforms() -> None:
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _reauth() -> None:
        await hass.config_entries.async_unload(entry_id)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry": entry,
                "unique_id": entry.unique_id,
            },
            data=data,
        )

    async def reauth() -> None:
        hass.async_create_task(_reauth())

    async def reload(message: Mapping) -> None:
        hass.async_create_task(hass.config_entries.async_reload(entry_id))

    hub.once(hub.EVENT_AUTHENTICATED, setup_platforms)
    hub.once(hub.EVENT_UNAUTHENTICATED, reauth)
    hub.once(hub.EVENT_ZONE_ADDED, reload)
    hub.once(hub.EVENT_ZONE_DELETED, reload)

    asyncio.create_task(hub.loop())  # not hass.async_create_task

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id]
    await hub.cancel()
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
