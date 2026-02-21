"""The Fish Audio integration."""

from __future__ import annotations

import logging

from fishaudio import AsyncFishAudio
from fishaudio.exceptions import AuthenticationError, FishAudioError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_API_KEY
from .types import FishAudioConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: FishAudioConfigEntry) -> bool:
    """Set up Fish Audio from a config entry."""
    client = AsyncFishAudio(api_key=entry.data[CONF_API_KEY])

    try:
        # Validate API key by getting account credits.
        await client.account.get_credits()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed(f"Invalid API key: {exc}") from exc
    except FishAudioError as exc:
        raise ConfigEntryNotReady(f"Error connecting to Fish Audio: {exc}") from exc

    entry.runtime_data = client

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
