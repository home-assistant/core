"""Text to speech support for Google Generative AI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.genai import types
from google.genai.errors import APIError, ClientError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CHAT_MODEL, LOGGER, RECOMMENDED_TTS_MODEL
from .entity import GoogleGenerativeAILLMBaseEntity
from .helpers import convert_to_wav


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [GoogleGenerativeAITextToSpeechEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAITextToSpeechEntity(
    TextToSpeechEntity, GoogleGenerativeAILLMBaseEntity
):
    """Google Generative AI text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]
    # See https://ai.google.dev/gemini-api/docs/speech-generation#languages
    # Note the documentation might not be up to date, e.g. el-GR is not listed
    # there but is supported.
    _attr_supported_languages = [
        "ar-EG",
        "bn-BD",
        "de-DE",
        "el-GR",
        "en-IN",
        "en-US",
        "es-US",
        "fr-FR",
        "hi-IN",
        "id-ID",
        "it-IT",
        "ja-JP",
        "ko-KR",
        "mr-IN",
        "nl-NL",
        "pl-PL",
        "pt-BR",
        "ro-RO",
        "ru-RU",
        "ta-IN",
        "te-IN",
        "th-TH",
        "tr-TR",
        "uk-UA",
        "vi-VN",
    ]
    # Unused, but required by base class.
    # The Gemini TTS models detect the input language automatically.
    _attr_default_language = "en-US"
    # See https://ai.google.dev/gemini-api/docs/speech-generation#voices
    _supported_voices = [
        Voice(voice.split(" ", 1)[0].lower(), voice)
        for voice in (
            "Zephyr (Bright)",
            "Puck (Upbeat)",
            "Charon (Informative)",
            "Kore (Firm)",
            "Fenrir (Excitable)",
            "Leda (Youthful)",
            "Orus (Firm)",
            "Aoede (Breezy)",
            "Callirrhoe (Easy-going)",
            "Autonoe (Bright)",
            "Enceladus (Breathy)",
            "Iapetus (Clear)",
            "Umbriel (Easy-going)",
            "Algieba (Smooth)",
            "Despina (Smooth)",
            "Erinome (Clear)",
            "Algenib (Gravelly)",
            "Rasalgethi (Informative)",
            "Laomedeia (Upbeat)",
            "Achernar (Soft)",
            "Alnilam (Firm)",
            "Schedar (Even)",
            "Gacrux (Mature)",
            "Pulcherrima (Forward)",
            "Achird (Friendly)",
            "Zubenelgenubi (Casual)",
            "Vindemiatrix (Gentle)",
            "Sadachbia (Lively)",
            "Sadaltager (Knowledgeable)",
            "Sulafat (Warm)",
        )
    ]

    def __init__(self, config_entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        super().__init__(config_entry, subentry, RECOMMENDED_TTS_MODEL)

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._supported_voices

    @cached_property
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: self._supported_voices[0].voice_id,
        }

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        config = self.create_generate_content_config()
        config.response_modalities = ["AUDIO"]
        config.speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=options[ATTR_VOICE]
                )
            )
        )

        def _extract_audio_parts(
            response: types.GenerateContentResponse,
        ) -> tuple[bytes, str]:
            if (
                not response.candidates
                or not response.candidates[0].content
                or not response.candidates[0].content.parts
                or not response.candidates[0].content.parts[0].inline_data
            ):
                raise ValueError("No content returned from TTS generation")

            data = response.candidates[0].content.parts[0].inline_data.data
            mime_type = response.candidates[0].content.parts[0].inline_data.mime_type

            if not isinstance(data, bytes):
                raise TypeError(
                    f"Expected bytes for audio data, got {type(data).__name__}"
                )
            if not isinstance(mime_type, str):
                raise TypeError(
                    f"Expected str for mime_type, got {type(mime_type).__name__}"
                )

            return data, mime_type

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL),
                contents=message,
                config=config,
            )

            data, mime_type = _extract_audio_parts(response)
        except (APIError, ClientError, ValueError, TypeError) as exc:
            LOGGER.error("Error during TTS: %s", exc, exc_info=True)
            raise HomeAssistantError(exc) from exc
        return "wav", convert_to_wav(data, mime_type)
