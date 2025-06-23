"""Text to speech support for Google Generative AI."""

from __future__ import annotations

from contextlib import suppress
import io
import logging
from typing import Any
import wave

from google.genai import types

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_MODEL, DOMAIN, RECOMMENDED_TTS_MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entity."""
    tts_entity = GoogleGenerativeAITextToSpeechEntity(config_entry)
    async_add_entities([tts_entity])


class GoogleGenerativeAITextToSpeechEntity(TextToSpeechEntity):
    """Google Generative AI text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_MODEL]
    # See https://ai.google.dev/gemini-api/docs/speech-generation#languages
    _attr_supported_languages = [
        "ar-EG",
        "bn-BD",
        "de-DE",
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

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Google Generative AI Conversation speech entity."""
        self.entry = entry
        self._attr_name = "Google Generative AI TTS"
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Google",
            model="Generative AI",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self._genai_client = entry.runtime_data
        self._default_voice_id = self._supported_voices[0].voice_id

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        return self._supported_voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        try:
            response = self._genai_client.models.generate_content(
                model=options.get(ATTR_MODEL, RECOMMENDED_TTS_MODEL),
                contents=message,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=options.get(
                                    ATTR_VOICE, self._default_voice_id
                                )
                            )
                        )
                    ),
                ),
            )

            data = response.candidates[0].content.parts[0].inline_data.data
            mime_type = response.candidates[0].content.parts[0].inline_data.mime_type
        except Exception as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "wav", self._convert_to_wav(data, mime_type)

    def _convert_to_wav(self, audio_data: bytes, mime_type: str) -> bytes:
        """Generate a WAV file header for the given audio data and parameters.

        Args:
            audio_data: The raw audio data as a bytes object.
            mime_type: Mime type of the audio data.

        Returns:
            A bytes object representing the WAV file header.

        """
        parameters = self._parse_audio_mime_type(mime_type)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(parameters["bits_per_sample"] // 8)
            wf.setframerate(parameters["rate"])
            wf.writeframes(audio_data)

        return wav_buffer.getvalue()

    def _parse_audio_mime_type(self, mime_type: str) -> dict[str, int]:
        """Parse bits per sample and rate from an audio MIME type string.

        Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

        Args:
            mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

        Returns:
            A dictionary with "bits_per_sample" and "rate" keys. Values will be
            integers if found, otherwise None.

        """
        if not mime_type.startswith("audio/L"):
            _LOGGER.warning("Received unexpected MIME type %s", mime_type)
            raise HomeAssistantError(f"Unsupported audio MIME type: {mime_type}")

        bits_per_sample = 16
        rate = 24000

        # Extract rate from parameters
        parts = mime_type.split(";")
        for param in parts:  # Skip the main type part
            param = param.strip()
            if param.lower().startswith("rate="):
                # Handle cases like "rate=" with no value or non-integer value and keep rate as default
                with suppress(ValueError, IndexError):
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
            elif param.startswith("audio/L"):
                # Keep bits_per_sample as default if conversion fails
                with suppress(ValueError, IndexError):
                    bits_per_sample = int(param.split("L", 1)[1])

        return {"bits_per_sample": bits_per_sample, "rate": rate}
