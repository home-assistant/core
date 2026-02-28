"""The Denon RS232 integration."""

from __future__ import annotations

import logging

from denon_rs232 import DenonReceiver, DenonState
from denon_rs232.models import MODELS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_MODEL,
    DOMAIN,  # noqa: F401
)

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type DenonRS232ConfigEntry = ConfigEntry[DenonReceiver]


async def async_setup_entry(hass: HomeAssistant, entry: DenonRS232ConfigEntry) -> bool:
    """Set up Denon RS232 from a config entry."""
    port = entry.data[CONF_PORT]
    model = MODELS[entry.data[CONF_MODEL]]
    receiver = DenonReceiver(port, model=model)

    try:
        await receiver.connect()
    except (ConnectionError, OSError) as err:
        _LOGGER.error("Error connecting to Denon receiver at %s: %s", port, err)
        raise ConfigEntryNotReady from err

    entry.runtime_data = receiver

    @callback
    def _on_disconnect(state: DenonState | None) -> None:
        if state is None:
            _LOGGER.warning("Denon receiver disconnected, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(receiver.subscribe(_on_disconnect))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DenonRS232ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.disconnect()

    return unload_ok
