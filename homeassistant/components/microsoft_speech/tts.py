"""Support for Microsoft Azure Cognitive Services text-to-speech."""

import asyncio
from enum import Enum
import logging

import azure.cognitiveservices.speech as speechsdk

from homeassistant.components.tts import (
    ATTR_VOICE,
    CONF_LANG,
    TextToSpeechEntity,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SPEECH_CONFIG, DATA_VOICES, DOMAIN, SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)


class AudioCodecs(str, Enum):
    """Audio codecs supported by the Microsoft TTS service."""

    MP3 = "mp3"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Microsoft Text To Speech platform via config entry."""
    async_add_entities([MicrosoftTextToSpeechEntity(config_entry)])


class MicrosoftTextToSpeechEntity(TextToSpeechEntity):
    """Microsoft Text To Speech."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Microsoft Azure TTS entity."""
        self._attr_unique_id = f"{entry.entry_id}"
        self._attr_name = entry.title
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Microsoft",
            model="Azure Speech Services",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self._entry = entry
        self._speech_config = entry.runtime_data[DATA_SPEECH_CONFIG]
        self._voices = entry.runtime_data[DATA_VOICES]

    @property
    def default_language(self):
        """Return the default language."""
        return self._entry.data[CONF_LANG]

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self):
        """Return list of supported options."""
        return [ATTR_VOICE]

    @property
    def supported_formats(self):
        """Return the list of supported audio formats."""
        return [AudioCodecs.MP3]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {}

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        return self._voices.get(language)

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from Microsoft."""
        self._speech_config.speech_synthesis_voice_name = options.get(ATTR_VOICE)
        self._speech_config.speech_synthesis_language = language
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self._speech_config
        )

        future = await asyncio.get_running_loop().run_in_executor(
            None,
            speech_synthesizer.speak_text_async,
            message,
        )
        result = future.get()
        if result.reason == speechsdk.ResultReason.Canceled:
            _LOGGER.error("Speech synthesis failed: %s", result.reason)
            return None, None
        return AudioCodecs.MP3, result.audio_data
