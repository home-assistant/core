"""The Nanoleaf integration."""
from __future__ import annotations

import asyncio

from aionanoleaf import EffectsEvent, InvalidToken, Nanoleaf, StateEvent, Unavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

PLATFORMS = ["button", "light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )
    try:
        await nanoleaf.get_info()
    except Unavailable as err:
        raise ConfigEntryNotReady from err
    except InvalidToken as err:
        raise ConfigEntryAuthFailed from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"device": nanoleaf}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _callback_update_light_state(event: StateEvent | EffectsEvent) -> None:
        """Receive state and effect event."""
        async_dispatcher_send(hass, f"{DOMAIN}_update_light_{nanoleaf.serial_no}")

    hass.data[DOMAIN][entry.entry_id]["event_listener"] = asyncio.create_task(
        nanoleaf.listen_events(
            state_callback=_callback_update_light_state,
            effects_callback=_callback_update_light_state,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data = hass.data[DOMAIN].pop(entry.entry_id)
    entry_data["event_listener"].cancel()
    return True
