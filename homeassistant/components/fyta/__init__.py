"""Initialization of FYTA integration."""
from __future__ import annotations

import logging

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import FytaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Fyta integration."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    fyta = FytaConnector(username, password)

    coordinator = FytaCoordinator(hass, fyta, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    try:
        await fyta.login()
    except FytaConnectionError as ex:
        raise ConfigEntryNotReady from ex
    except FytaAuthentificationError as ex:
        raise ConfigEntryAuthFailed from ex
    except FytaPasswordError as ex:
        raise ConfigEntryAuthFailed from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Fyta entity."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
