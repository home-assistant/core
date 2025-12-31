"""Set up the Elke27 integration."""

from __future__ import annotations

import contextlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_LINK_KEYS, CONF_PANEL, DOMAIN
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys = entry.data.get(CONF_LINK_KEYS)
    panel = entry.data.get(CONF_PANEL)
    hub = Elke27Hub(host, port, link_keys, panel)
    try:
        await hub.async_start()
    except Exception as err:
        _LOGGER.exception(
            "Failed to set up connection to %s:%s", host, port, exc_info=err
        )
        with contextlib.suppress(Exception):
            await hub.async_stop()
        raise ConfigEntryNotReady(
            "The client did not become ready; check host and port"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub: Elke27Hub | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if hub is not None:
        await hub.async_stop()
    return unload_ok
