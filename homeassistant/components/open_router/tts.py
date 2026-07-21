"""Text-to-speech support for OpenRouter."""

from collections.abc import Mapping
import logging
from typing import Any, Literal, override

from openai import OpenAIError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterConfigEntry
from .const import (
    CONF_TTS_SPEED,
    CONF_TTS_VOICE,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_TTS_VOICE,
)
from .entity import OpenRouterEntity

_LOGGER = logging.getLogger(__name__)

# Known TTS models and their voices. Updated as new models become available.
# Some providers/models may not expose voices via the API, so we maintain a
# fallback list.
_FALLBACK_VOICES = [
    Voice("alloy", "Alloy"),
    Voice("ash", "Ash"),
    Voice("ballad", "Ballad"),
    Voice("coral", "Coral"),
    Voice("echo", "Echo"),
    Voice("fable", "Fable"),
    Voice("nova", "Nova"),
    Voice("onyx", "Onyx"),
    Voice("sage", "Sage"),
    Voice("shimmer", "Shimmer"),
    Voice("verse", "Verse"),
    Voice("marin", "Marin"),
    Voice("cedar", "Cedar"),
]

_SUPPORTED_FORMATS = ["mp3", "pcm", "opus", "aac", "flac", "wav"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [OpenRouterTTSEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class OpenRouterTTSEntity(TextToSpeechEntity, OpenRouterEntity):
    """OpenRouter TTS entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT]
    _attr_supported_languages = [
        "af-ZA", "ar-SA", "hy-AM", "az-AZ", "be-BY", "bs-BA", "bg-BG",
        "ca-ES", "zh-CN", "hr-HR", "cs-CZ", "da-DK", "nl-NL", "en-US",
        "et-EE", "fi-FI", "fr-FR", "gl-ES", "de-DE", "el-GR", "he-IL",
        "hi-IN", "hu-HU", "is-IS", "id-ID", "it-IT", "ja-JP", "kn-IN",
        "kk-KZ", "ko-KR", "lv-LV", "lt-LT", "mk-MK", "ms-MY", "mr-IN",
        "mi-NZ", "ne-NP", "no-NO", "fa-IR", "pl-PL", "pt-PT", "ro-RO",
        "ru-RU", "sr-RS", "sk-SK", "sl-SI", "es-ES", "sw-KE", "sv-SE",
        "fil-PH", "ta-IN", "th-TH", "tr-TR", "uk-UA", "ur-PK", "vi-VN",
        "cy-GB",
    ]
    _attr_default_language = "en-US"

    _attr_has_entity_name = False
    _attr_translation_key = "openrouter_tts"

    def __init__(self, entry: OpenRouterConfigEntry, subentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return _FALLBACK_VOICES

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: self.subentry.data.get(
                CONF_TTS_VOICE, RECOMMENDED_TTS_VOICE
            ),
            ATTR_PREFERRED_FORMAT: "mp3",
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        options = {**self.subentry.data, **options}
        client = self.entry.runtime_data

        response_format = options.get(ATTR_PREFERRED_FORMAT, "mp3")
        if response_format in ("ogg", "oga"):
            codec: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "opus"
        elif response_format == "raw":
            response_format = codec = "pcm"
        elif response_format not in _SUPPORTED_FORMATS:
            response_format = codec = "mp3"
        else:
            codec = response_format

        try:
            async with client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=options[ATTR_VOICE],
                input=message,
                response_format=codec,
                speed=options.get(CONF_TTS_SPEED, RECOMMENDED_TTS_SPEED),
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": (
                        "https://www.home-assistant.io/integrations/open_router"
                    ),
                },
            ) as response:
                response_data = bytearray()
                async for chunk in response.iter_bytes():
                    response_data.extend(chunk)
        except OpenAIError as exc:
            _LOGGER.exception("Error during TTS")
            raise HomeAssistantError(exc) from exc

        return response_format, bytes(response_data)
