"""The Bryant Evolution integration."""

from __future__ import annotations

import logging

from evolutionhttp import BryantEvolutionClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SYSTEM_ID, CONF_ZONE_ID

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type BryantEvolutionConfigEntry = ConfigEntry[BryantEvolutionClient]  # noqa: F821
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: BryantEvolutionConfigEntry
) -> bool:
    """Set up Bryant Evolution from a config entry."""
    entry.runtime_data = BryantEvolutionClient(entry.data[CONF_HOST], entry.data[CONF_SYSTEM_ID], entry.data[CONF_ZONE_ID])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BryantEvolutionConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
