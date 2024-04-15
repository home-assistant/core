"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

import logging
from typing import Any

from elevenlabs.client import ElevenLabs
from elevenlabs.core import ApiError

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MODEL, CONF_VOICE, DEFAULT_LANG, SUPPORT_LANGUAGES

_LOGGER = logging.getLogger(__name__)

SUPPORT_OPTIONS = ["voice", "model"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    voice = config_entry.data[CONF_VOICE]
    model = config_entry.data[CONF_MODEL]
    async_add_entities([ElevenLabsTTSEntity(config_entry, model, voice)])


class ElevenLabsTTSEntity(TextToSpeechEntity):
    """The ElevenLabs API entity."""

    def __init__(self, config_entry: ConfigEntry, model: str, voice: str) -> None:
        """Init ElevenLabs TTS service."""
        self._model = model
        self._voice = voice
        self._api_key = config_entry.data[CONF_API_KEY]
        self._attr_name = f"ElevenLabs {model} {voice}"
        self._attr_unique_id = config_entry.entry_id

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return DEFAULT_LANG

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load TTS from ElevenLabs."""
        client = ElevenLabs(api_key=self._api_key)
        try:
            audio = client.generate(text=message, voice=self._voice, model=self._model)
            bytes_combined = b"".join(audio)
        except ApiError as exc:
            _LOGGER.exception("Error during processing of TTS request %s")
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined
