"""The Legrand RFLC integration.

https://www.legrand.us/solutions/smart-lighting/radio-frequency-lighting-controls
"""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, Final

import lc7001.aio

from homeassistant import config_entries
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry

from .const import DOMAIN

PLATFORMS: Final = ["light"]
_LOGGER: Final = logging.getLogger(__name__)


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

    async def authenticated(mac) -> None:
        unique_id = mac.lower()
        if unique_id != entry.unique_id:
            _LOGGER.warning(
                "Expected %s but found %s at %s",
                entry.unique_id,
                unique_id,
                host,
            )
            hass.async_create_task(_reauth())
            raise asyncio.CancelledError("reauth")
        device_registry.async_get(hass).async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Legrand",
            name=entry.title,
            model="LC7001",
        )
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _reauth() -> None:
        await hass.config_entries.async_unload(entry_id)
        entry.async_start_reauth(hass)

    async def reauth() -> None:
        hass.async_create_task(_reauth())

    async def reload(message: Mapping) -> None:
        hass.async_create_task(hass.config_entries.async_reload(entry_id))
        raise asyncio.CancelledError("reload")

    hub.once(hub.EVENT_AUTHENTICATED, authenticated)
    hub.once(hub.EVENT_UNAUTHENTICATED, reauth)
    hub.once(hub.EVENT_ZONE_ADDED, reload)
    hub.once(hub.EVENT_ZONE_DELETED, reload)

    async def start(*_: Any) -> None:
        async def loop():
            try:
                await hub.loop()
            except lc7001.aio.Authenticator.Error:
                pass

        hass.async_create_task(loop())

    # don't start (hass.async_create_task) unless/until hass is running
    if hass.state == CoreState.running:
        await start()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.cancel()
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True
