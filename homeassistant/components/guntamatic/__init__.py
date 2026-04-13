"""The guntamatic integration."""

from __future__ import annotations

import logging

from guntamatic.heater import Heater, NoSerialException
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .coordinator import GuntamaticConfigEntry, GuntamaticCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Set up guntamatic from a config entry."""

    heater = Heater(entry.data[CONF_HOST])

    try:
        initial_data = await hass.async_add_executor_job(heater.parse_data)
    except NoSerialException as err:
        raise ConfigEntryError(str(err)) from err
    except requests.exceptions.ConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to heater: {err}") from err
    except Exception as err:
        raise ConfigEntryError(f"Unexpected error: {err}") from err

    coordinator = GuntamaticCoordinator(hass, heater, entry)
    # Set initial data without doing extra network call
    coordinator.async_set_updated_data(initial_data)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
