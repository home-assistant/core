"""Text-to-speech support for Mistral AI."""

import base64
from collections.abc import AsyncGenerator, Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import get_voices
from .const import CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL
from .entity import MistralEntity

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral TTS platform."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [MistralTTSEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralTTSEntity(TextToSpeechEntity, MistralEntity):
    """Mistral AI text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT]
    _attr_supported_languages = ["fr", "en", "de", "es", "it"]
    _attr_default_language = "fr"

    _attr_has_entity_name = False

    def __init__(self, entry: MistralAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title
        self._voices: list[Voice] | None = None

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.hass.async_create_task(self._async_fetch_voices())

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        return self._voices

    async def _async_fetch_voices(self) -> list[Voice]:
        if self._voices is not None:
            return self._voices

        client = self.entry.runtime_data.client
        try:
            voices = await get_voices(client)
        except Exception:
            _LOGGER.exception("Error fetching voices")
            return []

        self._voices = [Voice(voice_id, name) for voice_id, name in voices]
        return self._voices

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        return {
            ATTR_VOICE: "",
            ATTR_PREFERRED_FORMAT: "mp3",
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        voice_id = options.get(ATTR_VOICE)
        if not voice_id:
            voices = await self._async_fetch_voices()
            if voices:
                voice_id = voices[0].voice_id

        options = {**self.subentry.data, **options}
        client = self.entry.runtime_data.client

        response_format = options.get(ATTR_PREFERRED_FORMAT, "mp3")
        if response_format == "ogg":
            response_format = "opus"

        try:
            response = await client.audio.speech.complete_async(
                model=options.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL),
                input=message,
                voice_id=voice_id or None,
                response_format=response_format,
            )
        except Exception as exc:
            _LOGGER.exception("Error during TTS")
            raise HomeAssistantError("Error talking to Mistral") from exc

        audio_data = base64.b64decode(response.audio_data)
        return response_format, audio_data

    @override
    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        options = {**self.subentry.data, **request.options}
        client = self.entry.runtime_data.client

        response_format = options.get(ATTR_PREFERRED_FORMAT, "mp3")
        if response_format == "ogg":
            response_format = "opus"

        message = "".join([chunk async for chunk in request.message_gen])

        try:
            stream = await client.audio.speech.complete_async(
                model=options.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL),
                input=message,
                voice_id=options.get(ATTR_VOICE) or None,
                response_format=response_format,
                stream=True,
            )
        except Exception as exc:
            _LOGGER.exception("Error during TTS streaming")
            raise HomeAssistantError("Error talking to Mistral") from exc

        async def data_gen() -> AsyncGenerator[bytes]:
            async for event in stream:
                if (
                    event.data
                    and getattr(event.data, "type", None) == "speech.audio.delta"
                ):
                    yield base64.b64decode(event.data.audio_data)

        return TTSAudioResponse(response_format, data_gen())
