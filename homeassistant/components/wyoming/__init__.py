"""The Wyoming integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load Wyoming."""
    platforms = []
    if "asr" in entry.data:
        platforms.append(Platform.STT)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        platforms,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wyoming."""
    platforms = []
    if "asr" in entry.data:
        platforms.append(Platform.STT)

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        platforms,
    )
    return unload_ok
