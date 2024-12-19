"""The Microsoft Speech integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import DOMAIN
from .helper import CannotConnect, InvalidAuth, TooManyRequests, validate_input

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.STT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Microsoft Speech from a config entry."""

    try:
        await validate_input(hass, dict(entry.data))
    except CannotConnect as err:
        _LOGGER.error("Failed to connect to Microsoft Speech API")
        raise ConfigEntryError from err
    except InvalidAuth as err:
        _LOGGER.error("Invalid API key or region provided")
        raise ConfigEntryAuthFailed from err
    except TooManyRequests as err:
        _LOGGER.error("Too many requests made to Microsoft Speech API")
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
