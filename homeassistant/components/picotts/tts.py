"""Support for the Pico TTS speech service."""

from __future__ import annotations

import io
import logging
from typing import Any
import wave

from py_nanotts import NanoTTS

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = ["en-US", "en-GB", "de-DE", "es-ES", "fr-FR", "it-IT"]
DEFAULT_LANG = "en-US"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up picoTTS TTS entity from a config entry."""
    async_add_entities([PicoTTSEntity()])


class PicoTTSEntity(TextToSpeechEntity):
    """picoTTS entity using NanoTTS."""

    _attr_name = "PicoTTS"
    _attr_unique_id = "picotts"
    _attr_supported_languages = SUPPORT_LANGUAGES
    _attr_default_language = DEFAULT_LANG

    _attr_supported_options = ["pitch", "speed", "volume"]

    def __init__(self) -> None:
        """Initialize entity."""
        self._engine = NanoTTS()

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Generate TTS audio.

        Return (content_type, bytes) or (None, None) on failure.
        """
        pitch = _coerce_float(options.get("pitch"))
        speed = _coerce_float(options.get("speed"))
        volume = _coerce_float(options.get("volume"))

        voice = language if language in SUPPORT_LANGUAGES else DEFAULT_LANG
        if voice != language:
            _LOGGER.debug(
                "Unsupported language %r requested; using %r", language, voice
            )

        try:
            pcm = self._engine.speak(
                message,
                voice=voice,
                speed=speed,
                pitch=pitch,
                volume=volume,
            )
        except Exception:
            _LOGGER.exception("NanoTTS failed generating audio")
            return (None, None)

        # Wrap returned PCM frames in a WAV container (mono, 16kHz, 16-bit)
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(16000)
                wav_file.setsampwidth(2)
                wav_file.setnchannels(1)
                wav_file.writeframes(pcm)

            return ("wav", wav_io.getvalue())


def _coerce_float(value: Any) -> float | None:
    """Convert service option values to float, returning None if unset/invalid."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None
