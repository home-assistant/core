"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

from functools import cached_property
import logging
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice

from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MODEL, CONF_VOICE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    model_id = config_entry.options.get(CONF_MODEL, config_entry.data[CONF_MODEL])
    default_voice_id = config_entry.options.get(
        CONF_VOICE, config_entry.data[CONF_VOICE]
    )
    client = AsyncElevenLabs(api_key=config_entry.data[CONF_API_KEY])

    # Load model and voices here in async context
    model: Model | None = None
    models = await client.models.get_all()
    for maybe_model in models:
        if maybe_model.model_id == model_id:
            model = maybe_model
            break

    if (model is None) or (not model.languages):
        raise ValueError(f"Failed to load model for id: {model_id}")

    voices = (await client.voices.get_all()).voices

    async_add_entities(
        [ElevenLabsTTSEntity(config_entry, client, model, voices, default_voice_id)]
    )


class ElevenLabsTTSEntity(tts.TextToSpeechEntity):
    """The ElevenLabs API entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: AsyncElevenLabs,
        model: Model,
        voices: list[Voice],
        default_voice_id: str,
    ) -> None:
        """Init ElevenLabs TTS service."""
        self._client = client
        self._model = model
        self._default_voice_id = default_voice_id
        self._voices = sorted(
            (tts.Voice(v.voice_id, v.name) for v in voices if v.name),
            key=lambda v: v.name,
        )
        self._attr_name = f"ElevenLabs {self._model.model_id}"
        self._attr_unique_id = config_entry.entry_id
        self._config_entry = config_entry

    @cached_property
    def default_language(self) -> str:
        """Return the default language."""
        return self.supported_languages[0]

    @cached_property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return [lang.language_id for lang in self._model.languages or []]

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return [tts.ATTR_VOICE]

    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Return a list of supported voices for a language."""
        return self._voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load tts audio file from the engine."""
        _LOGGER.debug("Getting TTS audio for %s", message)
        try:
            audio = await self._client.generate(
                text=message,
                voice=options.get(tts.ATTR_VOICE, self._default_voice_id),
                model=self._model.model_id,
            )
            bytes_combined = b"".join([byte_seg async for byte_seg in audio])
        except ApiError as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined
