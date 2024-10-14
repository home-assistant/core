"""The ElevenLabs text-to-speech integration."""

from __future__ import annotations

from dataclasses import dataclass

from elevenlabs import Model
from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_MODEL

PLATFORMS: list[Platform] = [Platform.TTS]


async def get_model_by_id(client: AsyncElevenLabs, model_id: str) -> Model | None:
    """Get ElevenLabs model from their API by the model_id."""
    models = await client.models.get_all()
    for maybe_model in models:
        if maybe_model.model_id == model_id:
            return maybe_model
    return None


@dataclass(kw_only=True, slots=True)
class ElevenLabsData:
    """ElevenLabs data type."""

    client: AsyncElevenLabs
    model: Model


type EleventLabsConfigEntry = ConfigEntry[ElevenLabsData]


async def async_setup_entry(hass: HomeAssistant, entry: EleventLabsConfigEntry) -> bool:
    """Set up ElevenLabs text-to-speech from a config entry."""
    entry.add_update_listener(update_listener)
    httpx_client = get_async_client(hass)
    client = AsyncElevenLabs(
        api_key=entry.data[CONF_API_KEY], httpx_client=httpx_client
    )
    model_id = entry.options[CONF_MODEL]
    try:
        model = await get_model_by_id(client, model_id)
    except ApiError as err:
        raise ConfigEntryError("Auth failed") from err

    if model is None or (not model.languages):
        raise ConfigEntryError("Model could not be resolved")

    entry.runtime_data = ElevenLabsData(client=client, model=model)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EleventLabsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(
    hass: HomeAssistant, config_entry: EleventLabsConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
