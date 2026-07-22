"""Text-to-speech support for OpenRouter."""

from collections.abc import AsyncGenerator, Mapping
import logging
from typing import Any, Literal, override

from openai import OpenAIError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    Voice,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.generated.languages import LANGUAGES
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterConfigEntry
from .const import (
    CONF_TTS_SPEED,
    CONF_TTS_VOICE,
    FALLBACK_TTS_VOICES,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_TTS_VOICE,
)
from .entity import OpenRouterEntity

_LOGGER = logging.getLogger(__name__)

# Voices offered when a model does not expose its own voices via the API
# (supported_voices is None).
_FALLBACK_VOICES = [Voice(v, v.title()) for v in FALLBACK_TTS_VOICES]

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
    # OpenRouter routes to many speech models and its API does not advertise
    # per-model language support, so we advertise every language Home Assistant
    # knows about and let the selected provider handle it.
    _attr_supported_languages = sorted(LANGUAGES)
    _attr_default_language = "en"

    _attr_name = None

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        voice_ids = self.subentry.data.get("supported_voices")
        if voice_ids:
            return [Voice(v, v) for v in voice_ids]
        return _FALLBACK_VOICES

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        voice_ids = self.subentry.data.get("supported_voices")
        default_voice = self.subentry.data.get(
            CONF_TTS_VOICE,
            voice_ids[0] if voice_ids else RECOMMENDED_TTS_VOICE,
        )
        return {
            ATTR_VOICE: default_voice,
            ATTR_PREFERRED_FORMAT: "mp3",
        }

    @override
    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Generate speech from an incoming message, streaming the audio response."""
        message = "".join([chunk async for chunk in request.message_gen])
        options = {**self.subentry.data, **request.options}
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

        async def data_gen() -> AsyncGenerator[bytes]:
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
                    async for chunk in response.iter_bytes():
                        yield chunk
            except OpenAIError as exc:
                _LOGGER.exception("Error during TTS")
                raise HomeAssistantError(exc) from exc

        return TTSAudioResponse(response_format, data_gen())
