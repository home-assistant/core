"""Set up the Elke27 integration."""

from __future__ import annotations

import contextlib
import logging

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_INTEGRATION_SERIAL, CONF_LINK_KEYS_JSON, DOMAIN
from .hub import Elke27Hub
from .identity import async_get_integration_serial

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data.get(CONF_LINK_KEYS_JSON)
    if not link_keys_json:
        raise ConfigEntryAuthFailed("Link keys are missing; relink required")
    if not entry.data.get(CONF_INTEGRATION_SERIAL):
        integration_serial = await async_get_integration_serial(hass, host)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_INTEGRATION_SERIAL: integration_serial},
        )
    hub = Elke27Hub(hass, host, port, link_keys_json)
    try:
        await hub.async_start()
    except Elke27LinkRequiredError as err:
        raise ConfigEntryAuthFailed(
            "Linking credentials are invalid; relink required"
        ) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.exception("Failed to set up connection to %s:%s", host, port)
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
