"""Support for the Pico TTS speech service."""

import io
from typing import Any, override
import wave

from py_nanotts import NanoTTS

from homeassistant.components.tts import CONF_LANG, TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SUPPORT_LANGUAGES

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
SAMPLE_CHANNELS = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pico TTS speech component via config entry."""
    async_add_entities([PicoTTSEntity(config_entry, config_entry.data[CONF_LANG])])


class PicoTTSEntity(TextToSpeechEntity):
    """The Pico TTS API entity."""

    _attr_supported_languages = SUPPORT_LANGUAGES

    def __init__(self, config_entry: ConfigEntry, lang: str) -> None:
        """Initialize Pico TTS service."""
        self._attr_default_language = lang
        self._attr_name = f"Pico TTS {lang}"
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            model="Pico TTS",
            name=f"Pico TTS {lang}",
        )
        self._engine = NanoTTS()

    @override
    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech with NanoTTS."""
        try:
            audio = self._engine.speak(message, voice=language)
        except RuntimeError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="synthesis_error",
                translation_placeholders={"error": str(exc)},
            ) from exc

        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setnchannels(SAMPLE_CHANNELS)
                wav_file.writeframes(audio)

            return "wav", wav_io.getvalue()
