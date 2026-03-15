"""The Emby integration."""

from __future__ import annotations

import aiohttp
from pyemby import EmbyServer
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS, CannotConnect, InvalidAuth

type EmbyConfigEntry = ConfigEntry[EmbyServer]


async def async_setup_entry(hass: HomeAssistant, entry: EmbyConfigEntry) -> bool:
    """Set up Emby from a config entry."""
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    port = entry.data[CONF_PORT]
    ssl = entry.data[CONF_SSL]

    try:
        await _validate_connection(hass, host, port, key, ssl)
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed("Invalid API key") from err
    except CannotConnect as err:
        raise ConfigEntryNotReady("Unable to connect") from err

    emby = EmbyServer(host, key, port, ssl, hass.loop)
    entry.runtime_data = emby

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def start_emby(event: Event | None = None) -> None:
        """Start Emby connection."""
        emby.start()

    if hass.is_running:
        start_emby()
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_emby)
        )

    entry.async_on_unload(emby.stop)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EmbyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _validate_connection(
    hass: HomeAssistant, host: str, port: int, api_key: str, ssl: bool
) -> str:
    """Validate the connection to the Emby server and return the server ID."""
    url = URL.build(
        scheme="https" if ssl else "http", host=host, port=port, path="/System/Info"
    )

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url,
            headers={"X-Emby-Token": api_key},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return data.get("Id", host)
    except aiohttp.ClientResponseError as err:
        if err.status == 401:
            raise InvalidAuth from err
        raise CannotConnect from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect from err
