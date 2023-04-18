"""The Wyoming integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load Wyoming."""
    stt_address = entry.options.get("stt_address")
    if stt_address:
        _LOGGER.debug("Loading STT platform")
        await async_load_platform(
            hass,
            Platform.STT,
            DOMAIN,
            {"address": stt_address},
            {},
        )

    tts_address = entry.options.get("tts_address")
    if tts_address:
        _LOGGER.debug("Loading TTS platform")
        await async_load_platform(
            hass,
            Platform.TTS,
            DOMAIN,
            {"address": tts_address},
            {},
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wyoming."""
    return True
