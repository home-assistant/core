"""The guntamatic integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from guntamatic.heater import Heater

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import GuntamaticCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR]

type GuntamaticConfigEntry = ConfigEntry[GuntamaticData]


@dataclass
class GuntamaticData:
    """Data for the Guntamatic integration."""

    heater: Heater
    coordinator: GuntamaticCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Set up guntamatic from a config entry."""

    host = entry.data[CONF_HOST]
    heater = Heater(host)

    # initial connectivity check
    initial_data = None
    try:
        initial_data = await hass.async_add_executor_job(heater.get_data)
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Guntamatic heater: {err}"
        ) from err

    if not initial_data:
        raise ConfigEntryNotReady("Cannot connect to Guntamatic heater")

    coordinator = GuntamaticCoordinator(hass, heater)
    coordinator.config_entry = entry

    coordinator.data = initial_data
    entry.runtime_data = GuntamaticData(heater=heater, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
