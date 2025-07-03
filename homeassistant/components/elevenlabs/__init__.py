"""The ElevenLabs text-to-speech integration."""

from __future__ import annotations

from dataclasses import dataclass

from elevenlabs import AsyncElevenLabs, Model
from elevenlabs.core import ApiError
from httpx import ConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_MODEL, CONF_STT_MODEL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.STT,
    Platform.TTS,
]


async def get_model_by_id(client: AsyncElevenLabs, model_id: str) -> Model | None:
    """Get ElevenLabs model from their API by the model_id."""
    models = await client.models.list()

    for maybe_model in models:
        if maybe_model.model_id == model_id:
            return maybe_model
    return None


@dataclass(kw_only=True, slots=True)
class ElevenLabsData:
    """ElevenLabs data type."""

    client: AsyncElevenLabs
    model: Model
    stt_model: str


type ElevenLabsConfigEntry = ConfigEntry[ElevenLabsData]


async def async_setup_entry(hass: HomeAssistant, entry: ElevenLabsConfigEntry) -> bool:
    """Set up ElevenLabs text-to-speech from a config entry."""
    entry.add_update_listener(update_listener)
    httpx_client = get_async_client(hass)
    client = AsyncElevenLabs(
        api_key=entry.data[CONF_API_KEY], httpx_client=httpx_client
    )
    model_id = entry.options[CONF_MODEL]
    try:
        model = await get_model_by_id(client, model_id)
    except ConnectError as err:
        raise ConfigEntryNotReady("Failed to connect") from err
    except ApiError as err:
        raise ConfigEntryAuthFailed("Auth failed") from err

    if model is None or (not model.languages):
        raise ConfigEntryError("Model could not be resolved")

    entry.runtime_data = ElevenLabsData(
        client=client, model=model, stt_model=entry.options[CONF_STT_MODEL]
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElevenLabsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(
    hass: HomeAssistant, config_entry: ElevenLabsConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ElevenLabsConfigEntry
) -> bool:
    """Migrate old config entry to new format."""

    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_options = {**config_entry.options}

        if config_entry.minor_version < 2:
            # Add defaults only if they’re not already present
            if "stt_auto_language" not in new_options:
                new_options["stt_auto_language"] = False
            if "stt_model" not in new_options:
                new_options["stt_model"] = "scribe_v1"

        hass.config_entries.async_update_entry(
            config_entry,
            options=new_options,
            minor_version=2,
            version=1,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True  # already up to date
