"""Text-to-speech support for OpenRouter."""

from collections.abc import Mapping
import io
from typing import Any, override
import wave

from openai import OpenAIError
from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
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
    DOMAIN,
    FALLBACK_TTS_VOICES,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_TTS_VOICE,
)
from .entity import OpenRouterEntity

# Voices offered when a model does not expose its own voices via the API
# (supported_voices is None).
_FALLBACK_VOICES = [Voice(v, v.title()) for v in FALLBACK_TTS_VOICES]

# OpenRouter returns only mp3 or pcm, and some providers support just one.
# The models API does not expose this, so it is keyed on the model id prefix.
_PCM_ONLY_PROVIDERS = ("google/", "heygen/")

# OpenRouter does not document the PCM layout. This matches Gemini TTS output.
_PCM_SAMPLE_RATE = 24000
_PCM_SAMPLE_WIDTH = 2
_PCM_CHANNELS = 1


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

    _attr_supported_options = [ATTR_VOICE]
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
        return {ATTR_VOICE: default_voice}

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS audio from OpenRouter."""
        options = {**self.subentry.data, **options}
        client = self.entry.runtime_data
        pcm = self.model.startswith(_PCM_ONLY_PROVIDERS)

        try:
            response = await client.audio.speech.create(
                model=self.model,
                voice=options[ATTR_VOICE],
                input=message,
                response_format="pcm" if pcm else "mp3",
                speed=options.get(CONF_TTS_SPEED, RECOMMENDED_TTS_SPEED),
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": (
                        "https://www.home-assistant.io/integrations/open_router"
                    ),
                },
            )
        except OpenAIError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(exc)},
            ) from exc

        if not pcm:
            return "mp3", response.content

        # Wrap raw PCM in a WAV header so Home Assistant can convert it.
        with io.BytesIO() as wav_io:
            wav_file: wave.Wave_write = wave.open(wav_io, "wb")
            with wav_file:
                wav_file.setframerate(_PCM_SAMPLE_RATE)
                wav_file.setsampwidth(_PCM_SAMPLE_WIDTH)
                wav_file.setnchannels(_PCM_CHANNELS)
                wav_file.writeframes(response.content)
            return "wav", wav_io.getvalue()
