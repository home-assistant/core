"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from elevenlabs import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice as ElevenLabsVoice, VoiceSettings

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElevenLabsConfigEntry
from .const import (
    ATTR_MODEL,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


def to_voice_settings(options: Mapping[str, Any]) -> VoiceSettings:
    """Return voice settings."""
    return VoiceSettings(
        stability=options.get(CONF_STABILITY, DEFAULT_STABILITY),
        similarity_boost=options.get(CONF_SIMILARITY, DEFAULT_SIMILARITY),
        style=options.get(CONF_STYLE, DEFAULT_STYLE),
        use_speaker_boost=options.get(
            CONF_USE_SPEAKER_BOOST, DEFAULT_USE_SPEAKER_BOOST
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElevenLabsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    client = config_entry.runtime_data.client
    voices = (await client.voices.get_all()).voices
    default_voice_id = config_entry.options[CONF_VOICE]
    voice_settings = to_voice_settings(config_entry.options)
    async_add_entities(
        [
            ElevenLabsTTSEntity(
                client,
                config_entry.runtime_data.model,
                voices,
                default_voice_id,
                config_entry.entry_id,
                config_entry.title,
                voice_settings,
            )
        ]
    )


class ElevenLabsTTSEntity(TextToSpeechEntity):
    """The ElevenLabs API entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_MODEL]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        client: AsyncElevenLabs,
        model: Model,
        voices: list[ElevenLabsVoice],
        default_voice_id: str,
        entry_id: str,
        title: str,
        voice_settings: VoiceSettings,
    ) -> None:
        """Init ElevenLabs TTS service."""
        self._client = client
        self._model = model
        self._default_voice_id = default_voice_id
        self._voices = sorted(
            (Voice(v.voice_id, v.name) for v in voices if v.name),
            key=lambda v: v.name,
        )
        # Default voice first
        voice_indices = [
            idx for idx, v in enumerate(self._voices) if v.voice_id == default_voice_id
        ]
        if voice_indices:
            self._voices.insert(0, self._voices.pop(voice_indices[0]))
        self._voice_settings = voice_settings

        # Entity attributes
        self._attr_unique_id = entry_id
        self._attr_name = title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="ElevenLabs",
            model=model.name,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_supported_languages = [
            lang.language_id for lang in self._model.languages or []
        ]
        self._attr_default_language = self.supported_languages[0]

    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        _LOGGER.debug("Getting TTS audio for %s", message)
        _LOGGER.debug("Options: %s", options)
        voice_id = options.get(ATTR_VOICE, self._default_voice_id)
        model = options.get(ATTR_MODEL, self._model.model_id)
        try:
            audio = self._client.text_to_speech.convert(
                text=message,
                voice_id=voice_id,
                voice_settings=self._voice_settings,
                model_id=model,
            )
            bytes_combined = b"".join([byte_seg async for byte_seg in audio])

        except ApiError as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined
