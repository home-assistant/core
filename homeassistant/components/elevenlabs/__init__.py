"""The ElevenLabs text-to-speech integration."""

from __future__ import annotations

from dataclasses import dataclass

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CONF_MODEL, DEFAULT_MODEL
from .tts import get_model_by_id

PLATFORMS: list[Platform] = [Platform.TTS]


@dataclass(kw_only=True, slots=True)
class ElevenLabsData:
    """ElevenLabs data type."""

    client: AsyncElevenLabs


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ElevenLabs text-to-speech from a config entry."""
    entry.add_update_listener(update_listener)
    client = AsyncElevenLabs(api_key=entry.data[CONF_API_KEY])
    model_id = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL))
    # Fallback to default
    model_id = model_id if model_id is not None else DEFAULT_MODEL
    try:
        model = await get_model_by_id(client, model_id)
    except ApiError as err:
        raise ConfigEntryAuthFailed from err

    if model is None or (not model.languages):
        return False

    entry.runtime_data = ElevenLabsData(client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
