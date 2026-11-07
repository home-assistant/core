"""Text to speech support for OpenAI."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, Literal, override

from openai import AuthenticationError, OpenAIError, omit
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.const import CONF_PROMPT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .capabilities import get_tts_voices
from .const import (
    CONF_CHAT_MODEL,
    CONF_TTS_MODEL,
    CONF_TTS_SPEED,
    DOMAIN,
    RECOMMENDED_TTS_SPEED,
)
from .entity import OpenAIBaseLLMEntity

if TYPE_CHECKING:
    from . import OpenAIConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
    """Azure OpenAI TTS entity."""

    _attr_name = "Text-to-speech"
    _attr_translation_key = "tts"
    _attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT]
    # https://platform.openai.com/docs/guides/text-to-speech#supported-languages
    # The model may also generate the audio in different
    # languages but with lower quality
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

    _supported_formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return [
            Voice(voice, voice.title())
            for voice in get_tts_voices(self.subentry.data[CONF_TTS_MODEL])
        ]

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: get_tts_voices(self.subentry.data[CONF_TTS_MODEL])[0],
            ATTR_PREFERRED_FORMAT: "mp3",
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""

        options = {**self.subentry.data, **options}
        client = self.entry.runtime_data

        response_format = options[ATTR_PREFERRED_FORMAT]
        if response_format in ("ogg", "oga"):
            codec: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "opus"
        elif response_format == "raw":
            response_format = codec = "pcm"
        elif response_format not in self._supported_formats:
            response_format = self.default_options[ATTR_PREFERRED_FORMAT]
            codec = response_format
        else:
            codec = response_format

        try:
            async with client.audio.speech.with_streaming_response.create(
                model=options[CONF_CHAT_MODEL],
                voice=options[ATTR_VOICE],
                input=message,
                instructions=options.get(CONF_PROMPT) or omit,
                speed=options.get(CONF_TTS_SPEED, RECOMMENDED_TTS_SPEED),
                response_format=codec,
            ) as response:
                response_data = bytearray()
                async for chunk in response.iter_bytes():
                    response_data.extend(chunk)
        except AuthenticationError as exc:
            self.entry.async_start_reauth(self.hass)
            _LOGGER.exception("Authentication failed during TTS")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="tts_error",
            ) from exc
        except OpenAIError as exc:
            _LOGGER.exception("Error during TTS")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="tts_error",
            ) from exc

        return response_format, bytes(response_data)
