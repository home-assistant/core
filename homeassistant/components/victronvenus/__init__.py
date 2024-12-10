"""The victronvenus integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from ._hubcontrol import _async_setup_hub, _async_unload_hub
from .const import DOMAIN
from .victronvenus_base import VictronVenusConfigEntry as _VictronVenusConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

__all__ = ["async_setup_entry", "async_unload_entry", "DOMAIN"]


async def async_setup_entry(
    hass: HomeAssistant, entry: _VictronVenusConfigEntry
) -> bool:
    """Set up victronvenus from a config entry."""
    return await _async_setup_hub(hass, entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: _VictronVenusConfigEntry
) -> bool:
    """Unload a config entry."""

    return await _async_unload_hub(hass, entry, PLATFORMS)
