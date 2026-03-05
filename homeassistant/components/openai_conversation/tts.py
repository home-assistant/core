"""Text to speech support for OpenAI."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from openai import OpenAIError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CHAT_MODEL, CONF_PROMPT, CONF_TTS_SPEED, RECOMMENDED_TTS_SPEED
from .entity import OpenAIBaseLLMEntity

if TYPE_CHECKING:
    from . import OpenAIConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [OpenAITTSEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenAITTSEntity(TextToSpeechEntity, OpenAIBaseLLMEntity):
    """OpenAI TTS entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT]
    # https://platform.openai.com/docs/guides/text-to-speech#supported-languages
    # The model may also generate the audio in different languages but with lower quality
    _attr_supported_languages = [
        "af-ZA",  # Afrikaans
        "ar-SA",  # Arabic
        "hy-AM",  # Armenian
        "az-AZ",  # Azerbaijani
        "be-BY",  # Belarusian
        "bs-BA",  # Bosnian
        "bg-BG",  # Bulgarian
        "ca-ES",  # Catalan
        "zh-CN",  # Chinese (Mandarin)
        "hr-HR",  # Croatian
        "cs-CZ",  # Czech
        "da-DK",  # Danish
        "nl-NL",  # Dutch
        "en-US",  # English
        "et-EE",  # Estonian
        "fi-FI",  # Finnish
        "fr-FR",  # French
        "gl-ES",  # Galician
        "de-DE",  # German
        "el-GR",  # Greek
        "he-IL",  # Hebrew
        "hi-IN",  # Hindi
        "hu-HU",  # Hungarian
        "is-IS",  # Icelandic
        "id-ID",  # Indonesian
        "it-IT",  # Italian
        "ja-JP",  # Japanese
        "kn-IN",  # Kannada
        "kk-KZ",  # Kazakh
        "ko-KR",  # Korean
        "lv-LV",  # Latvian
        "lt-LT",  # Lithuanian
        "mk-MK",  # Macedonian
        "ms-MY",  # Malay
        "mr-IN",  # Marathi
        "mi-NZ",  # Maori
        "ne-NP",  # Nepali
        "no-NO",  # Norwegian
        "fa-IR",  # Persian
        "pl-PL",  # Polish
        "pt-PT",  # Portuguese
        "ro-RO",  # Romanian
        "ru-RU",  # Russian
        "sr-RS",  # Serbian
        "sk-SK",  # Slovak
        "sl-SI",  # Slovenian
        "es-ES",  # Spanish
        "sw-KE",  # Swahili
        "sv-SE",  # Swedish
        "fil-PH",  # Tagalog (Filipino)
        "ta-IN",  # Tamil
        "th-TH",  # Thai
        "tr-TR",  # Turkish
        "uk-UA",  # Ukrainian
        "ur-PK",  # Urdu
        "vi-VN",  # Vietnamese
        "cy-GB",  # Welsh
    ]
    # Unused, but required by base class.
    # The models detect the input language automatically.
    _attr_default_language = "en-US"

    # https://platform.openai.com/docs/guides/text-to-speech#voice-options
    _supported_voices = [
        Voice(voice.lower(), voice)
        for voice in (
            "Marin",
            "Cedar",
            "Alloy",
            "Ash",
            "Ballad",
            "Coral",
            "Echo",
            "Fable",
            "Nova",
            "Onyx",
            "Sage",
            "Shimmer",
            "Verse",
        )
    ]

    _supported_formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

    _attr_has_entity_name = False

    def __init__(self, entry: OpenAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._supported_voices

    @cached_property
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: self._supported_voices[0].voice_id,
            ATTR_PREFERRED_FORMAT: "mp3",
        }

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""

        options = {**self.subentry.data, **options}
        client = self.entry.runtime_data

        response_format = options[ATTR_PREFERRED_FORMAT]
        if response_format not in self._supported_formats:
            # common aliases
            if response_format == "ogg":
                response_format = "opus"
            elif response_format == "raw":
                response_format = "pcm"
            else:
                response_format = self.default_options[ATTR_PREFERRED_FORMAT]

        try:
            async with client.audio.speech.with_streaming_response.create(
                model=options[CONF_CHAT_MODEL],
                voice=options[ATTR_VOICE],
                input=message,
                instructions=str(options.get(CONF_PROMPT)),
                speed=options.get(CONF_TTS_SPEED, RECOMMENDED_TTS_SPEED),
                response_format=response_format,
            ) as response:
                response_data = bytearray()
                async for chunk in response.iter_bytes():
                    response_data.extend(chunk)
        except OpenAIError as exc:
            _LOGGER.exception("Error during TTS")
            raise HomeAssistantError(exc) from exc

        return response_format, bytes(response_data)
