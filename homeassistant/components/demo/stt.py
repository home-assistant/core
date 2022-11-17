"""Support for the demo for speech to text service."""
from __future__ import annotations

from aiohttp import StreamReader

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SUPPORT_LANGUAGES = ["en", "de"]


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Provider:
    """Set up Demo speech component."""
    return DemoProvider()


class DemoProvider(Provider):
    """Demo speech API provider."""

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000, AudioSampleRates.SAMPLERATE_44100]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: StreamReader
    ) -> SpeechResult:
        """Process an audio stream to STT service."""

        # Read available data
        async for _ in stream.iter_chunked(4096):
            pass

        return SpeechResult("Turn the Kitchen Lights on", SpeechResultState.SUCCESS)
