"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice as ElevenLabsVoice, VoiceSettings

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EleventLabsConfigEntry
from .const import (
    CONF_OPTIMIZE_LATENCY,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_OPTIMIZE_LATENCY,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def to_voice_settings(options: MappingProxyType[str, Any]) -> VoiceSettings:
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
    config_entry: EleventLabsConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
                config_entry.options.get(
                    CONF_OPTIMIZE_LATENCY, DEFAULT_OPTIMIZE_LATENCY
                ),
            )
        ]
    )


class ElevenLabsTTSEntity(TextToSpeechEntity):
    """The ElevenLabs API entity."""

    _attr_supported_options = [ATTR_VOICE]

    def __init__(
        self,
        client: AsyncElevenLabs,
        model: Model,
        voices: list[ElevenLabsVoice],
        default_voice_id: str,
        entry_id: str,
        title: str,
        voice_settings: VoiceSettings,
        latency: int = 0,
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
        self._latency = latency

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
        try:
            audio = await self._client.generate(
                text=message,
                voice=voice_id,
                optimize_streaming_latency=self._latency,
                voice_settings=self._voice_settings,
                model=self._model.model_id,
            )
            bytes_combined = b"".join([byte_seg async for byte_seg in audio])
        except ApiError as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined
