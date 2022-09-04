"""The MPRIS media playback remote control integration."""
from __future__ import annotations

import datetime

import hassmpris_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .cert_data import CertStore
from .const import (
    CONF_HOST,
    CONF_MPRIS_PORT,
    DOMAIN,
    ENTRY_CLIENT,
    ENTRY_UNLOAD_FUNC,
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
        client_cert, client_key, trust_chain = await CertStore(
            hass, entry.unique_id
        ).load_cert_data()
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
    component_data = hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_CLIENT: clnt,
        ENTRY_UNLOADERS: [],
    }

    async def _async_unload(*unused_args):
        _LOGGER.debug("Running unloaders")
        while component_data[ENTRY_UNLOADERS]:
            unloader = component_data[ENTRY_UNLOADERS].pop()
            await unloader()
        _LOGGER.debug("Unloaders complete")

    component_data[ENTRY_UNLOAD_FUNC] = _async_unload

    async def async_close_client():
        if ENTRY_CLIENT in component_data:
            clnt = component_data[ENTRY_CLIENT]
            _LOGGER.debug("Closing connection to agent")
            await clnt.close()
            _LOGGER.debug("Connection closed")
            component_data.pop(ENTRY_CLIENT)

    component_data[ENTRY_UNLOADERS].append(async_close_client)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_unload)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        component_data = hass.data[DOMAIN].pop(entry.entry_id)
        unload_func = component_data[ENTRY_UNLOAD_FUNC]
        await unload_func()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # This would be an error, and the type checker knows it.
    assert entry.unique_id
    await CertStore(hass, entry.unique_id).remove_cert_data()
