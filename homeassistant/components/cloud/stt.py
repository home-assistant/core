"""Support for the cloud for speech to text service."""
from __future__ import annotations

from aiohttp import StreamReader
from hass_nabucasa import Cloud
from hass_nabucasa.voice import VoiceError

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
)

from .const import DOMAIN

SUPPORT_LANGUAGES = [
    "da-DK",
    "de-DE",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-US",
    "es-ES",
    "fi-FI",
    "fr-CA",
    "fr-FR",
    "it-IT",
    "ja-JP",
    "nl-NL",
    "pl-PL",
    "pt-PT",
    "ru-RU",
    "sv-SE",
    "th-TH",
    "zh-CN",
    "zh-HK",
]


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Cloud speech component."""
    cloud: Cloud = hass.data[DOMAIN]

    return CloudProvider(cloud)


class CloudProvider(Provider):
    """NabuCasa speech API provider."""

    def __init__(self, cloud: Cloud) -> None:
        """Home Assistant NabuCasa Speech to text."""
        self.cloud = cloud

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: StreamReader
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        content = f"audio/{metadata.format!s}; codecs=audio/{metadata.codec!s}; samplerate=16000"

        # Process STT
        try:
            result = await self.cloud.voice.process_stt(
                stream, content, metadata.language
            )
        except VoiceError:
            return SpeechResult(None, SpeechResultState.ERROR)

        # Return Speech as Text
        return SpeechResult(
            result.text,
            SpeechResultState.SUCCESS if result.success else SpeechResultState.ERROR,
        )
