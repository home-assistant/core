"""The Legrand RFLC integration.

https://www.legrand.us/solutions/smart-lighting/radio-frequency-lighting-controls
"""

import asyncio
from collections.abc import Mapping
from typing import Final

import lc7001.aio

from homeassistant import config_entries
from homeassistant.const import CONF_AUTHENTICATION, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: Final = ["light"]


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
    hass.data.setdefault(DOMAIN, {})[entry_id] = hub = lc7001.aio.Hub(host, **kwargs)

    async def setup_platforms() -> None:
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _reauth() -> None:
        await hass.config_entries.async_unload(entry_id)
        entry.async_start_reauth(hass)

    async def reauth() -> None:
        hass.async_create_task(_reauth())

    async def reload(message: Mapping) -> None:
        hass.async_create_task(hass.config_entries.async_reload(entry_id))
        raise asyncio.CancelledError("reload")

    hub.once(hub.EVENT_AUTHENTICATED, setup_platforms)
    hub.once(hub.EVENT_UNAUTHENTICATED, reauth)
    hub.once(hub.EVENT_ZONE_ADDED, reload)
    hub.once(hub.EVENT_ZONE_DELETED, reload)

    async def loop():
        try:
            await hub.loop()
        except lc7001.aio.Authenticator.Error:
            pass

    hass.async_create_task(loop())

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.cancel()
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True
