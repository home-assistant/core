"""The MPRIS media playback remote control integration."""
from __future__ import annotations

import datetime

import hassmpris_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .cert_data import load_cert_data
from .const import (
    CONF_HOST,
    CONF_MPRIS_PORT,
    DOMAIN,
    ENTRY_CLIENT,
    ENTRY_UNLOADERS,
    LOGGER as _LOGGER,
)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=5)
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MPRIS media playback remote control from a config entry."""

    # This would be an error, and the type checker knows it.
    assert entry.unique_id is not None

    try:
        client_cert, client_key, trust_chain = await load_cert_data(
            hass, entry.unique_id
        )
    except KeyError as exc:
        raise ConfigEntryAuthFailed(
            "Authentication data is missing -- must reauth"
        ) from exc

    clnt = hassmpris_client.AsyncMPRISClient(
        entry.data[CONF_HOST],
        entry.data[CONF_MPRIS_PORT],
        client_cert,
        client_key,
        trust_chain,
    )
    try:
        _LOGGER.debug("Pinging the MPRIS agent")
        await clnt.ping()
        _LOGGER.info("Successfully pinged the MPRIS agent")

    except hassmpris_client.Unauthenticated as exc:
        raise ConfigEntryAuthFailed(exc) from exc
    except Exception as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_CLIENT: clnt,
        ENTRY_UNLOADERS: [],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Closing connection to agent")
        await data[ENTRY_CLIENT].close()
        _LOGGER.debug("Connection closed -- running unloaders")
        unloaders = data[ENTRY_UNLOADERS]
        for unloader in reversed(unloaders):
            await unloader()
        _LOGGER.debug("Unloaders complete")

    return unload_ok
