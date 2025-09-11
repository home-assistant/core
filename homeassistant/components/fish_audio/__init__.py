"""The Fish Audio integration."""

from __future__ import annotations

import logging

from fish_audio_sdk import Session
from fish_audio_sdk.exceptions import HttpCodeErr

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .types import FishAudioConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: FishAudioConfigEntry) -> bool:
    """Set up Fish Audio from a config entry."""
    session = Session(entry.data[CONF_API_KEY])

    try:
        await hass.async_add_executor_job(session.get_api_credit)
    except HttpCodeErr as exc:
        if exc.status == 401:
            raise ConfigEntryAuthFailed(f"Invalid API key: {exc.message}") from exc
        raise ConfigEntryNotReady(
            f"Failed to connect to Fish Audio API: {exc}"
        ) from exc
    except Exception as exc:
        _LOGGER.exception("Unexpected error while setting up Fish Audio")
        raise ConfigEntryNotReady("Unexpected error during setup") from exc

    entry.runtime_data = session

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: FishAudioConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FishAudioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
