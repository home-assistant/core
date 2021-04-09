"""Helper for detecting memory leaks."""
from __future__ import annotations

import logging
from typing import Callable

import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

DATA_CLIENTSESSION_CONFIG_ENTRY = "aiohttp_clientsession_config_entry"

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_clientsession_leak_detection(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> Callable:
    """Register ClientSession close on Home Assistant shutdown.

    This method must be run in the event loop.
    """
    sessions: dict[str, list[aiohttp.ClientSession]] = hass.data.setdefault(
        DATA_CLIENTSESSION_CONFIG_ENTRY, {}
    )

    config_entry = config_entries.current_entry.get()
    if not config_entry:

        @callback
        def _cleanup_without_entry() -> None:
            clientsession.detach()

        return _cleanup_without_entry

    entry_id = config_entry.entry_id
    sessions.setdefault(entry_id, []).append(clientsession)

    @callback
    def _cleanup_with_entry() -> None:
        clientsession.detach()
        sessions[entry_id].remove(clientsession)

    return _cleanup_with_entry


@callback
def async_check_for_aiohttp_leaks(
    hass: HomeAssistant, entry_id: str, domain: str
) -> None:
    """Check for a memory leak when unloading a config entry."""
    if DATA_CLIENTSESSION_CONFIG_ENTRY not in hass.data:
        return
    if entry_id not in hass.data[DATA_CLIENTSESSION_CONFIG_ENTRY]:
        return
    for clientsession in hass.data[DATA_CLIENTSESSION_CONFIG_ENTRY][entry_id]:
        _LOGGER.error(
            "Config entry %s for %s leaked client session %s",
            entry_id,
            domain,
            clientsession,
        )
        clientsession.detach()
