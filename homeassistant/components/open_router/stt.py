"""Speech-to-text support for OpenRouter."""

from collections.abc import AsyncIterable
import io
import logging
from typing import override
import wave

from openai import OpenAIError

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterConfigEntry
from .entity import OpenRouterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT entities."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "stt":
            continue

        async_add_entities(
            [OpenRouterSTTEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class OpenRouterSTTEntity(SpeechToTextEntity, OpenRouterEntity):
    """OpenRouter STT entity."""

    _attr_has_entity_name = False
    _attr_translation_key = "openrouter_stt"

    def __init__(self, entry: OpenRouterConfigEntry, subentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return [
            "af", "ar", "hy", "az", "be", "bs", "bg", "ca", "zh", "hr",
            "cs", "da", "nl", "en", "et", "fi", "fr", "gl", "de", "el",
            "he", "hi", "hu", "is", "id", "it", "ja", "kn", "kk", "ko",
            "lv", "lt", "mk", "ms", "mr", "mi", "ne", "no", "fa", "pl",
            "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw", "sv", "tl",
            "ta", "th", "tr", "uk", "ur", "vi", "cy",
        ]

    @property
    @override
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    @override
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    @override
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""
        return [
            AudioBitRates.BITRATE_8,
            AudioBitRates.BITRATE_16,
            AudioBitRates.BITRATE_24,
            AudioBitRates.BITRATE_32,
        ]

    @property
    @override
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [
            AudioSampleRates.SAMPLERATE_8000,
            AudioSampleRates.SAMPLERATE_11000,
            AudioSampleRates.SAMPLERATE_16000,
            AudioSampleRates.SAMPLERATE_18900,
            AudioSampleRates.SAMPLERATE_22000,
            AudioSampleRates.SAMPLERATE_32000,
            AudioSampleRates.SAMPLERATE_37800,
            AudioSampleRates.SAMPLERATE_44100,
            AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    @override
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO, AudioChannels.CHANNEL_STEREO]

    @override
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        audio_bytes = bytearray()
        async for chunk in stream:
            audio_bytes.extend(chunk)
        audio_data = bytes(audio_bytes)

        if metadata.format == AudioFormats.WAV:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(metadata.channel.value)
                wf.setsampwidth(metadata.bit_rate.value // 8)
                wf.setframerate(metadata.sample_rate.value)
                wf.writeframes(audio_data)
            audio_data = wav_buffer.getvalue()

        client = self.entry.runtime_data

        try:
            response = await client.audio.transcriptions.create(
                model=self.model,
                file=(f"a.{metadata.format.value}", audio_data),
                response_format="json",
                language=metadata.language.split("-")[0],
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": (
                        "https://www.home-assistant.io/integrations/open_router"
                    ),
                },
            )
        except OpenAIError:
            _LOGGER.exception("Error during STT")
            return SpeechResult(None, SpeechResultState.ERROR)

        if response.text:
            return SpeechResult(response.text, SpeechResultState.SUCCESS)

        return SpeechResult(None, SpeechResultState.ERROR)
