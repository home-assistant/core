"""Support for the ElevenLabs text-to-speech service."""

from __future__ import annotations

from functools import cached_property
import logging
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model, Voice

from homeassistant.components import tts
from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EleventLabsConfigEntry
from .const import CONF_VOICE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EleventLabsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    client = config_entry.runtime_data.client
    voices = (await client.voices.get_all()).voices
    default_voice_id = config_entry.options.get(CONF_VOICE, voices[0].voice_id)
    async_add_entities(
        [
            ElevenLabsTTSEntity(
                client,
                config_entry.runtime_data.model,
                voices,
                default_voice_id,
                config_entry.entry_id,
            )
        ]
    )


class ElevenLabsTTSEntity(TextToSpeechEntity):
    """The ElevenLabs API entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        client: AsyncElevenLabs,
        model: Model,
        voices: list[Voice],
        default_voice_id: str,
        entry_id: str,
    ) -> None:
        """Init ElevenLabs TTS service."""
        self._client = client
        self._model = model
        self._default_voice_id = default_voice_id
        self._voices = sorted(
            (tts.Voice(v.voice_id, v.name) for v in voices if v.name),
            key=lambda v: v.name,
        )
        # Default voice first
        voice_indices = [
            idx for idx, v in enumerate(self._voices) if v.voice_id == default_voice_id
        ]
        if voice_indices:
            self._voices.insert(0, self._voices.pop(voice_indices[0]))
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @cached_property
    def default_language(self) -> str:
        """Return the default language."""
        return self.supported_languages[0]

    @cached_property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return [lang.language_id for lang in self._model.languages or []]

    @property
    def supported_options(self) -> list[str]:
        """Return a list of supported options."""
        return [tts.ATTR_VOICE]

    def async_get_supported_voices(self, language: str) -> list[tts.Voice]:
        """Return a list of supported voices for a language."""
        return self._voices

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load tts audio file from the engine."""
        _LOGGER.debug("Getting TTS audio for %s", message)
        voice_id = options[tts.ATTR_VOICE]
        try:
            audio = await self._client.generate(
                text=message,
                voice=voice_id,
                model=self._model.model_id,
            )
            bytes_combined = b"".join([byte_seg async for byte_seg in audio])
        except ApiError as exc:
            _LOGGER.warning(
                "Error during processing of TTS request %s", exc, exc_info=True
            )
            raise HomeAssistantError(exc) from exc
        return "mp3", bytes_combined
