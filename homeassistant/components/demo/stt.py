"""Support for the demo for speech to text service."""
from typing import List

from aiohttp import StreamReader

from homeassistant.components.stt import Provider, SpeechMetadata, SpeechResult
from homeassistant.components.stt.const import (
    AudioBitrates,
    AudioFormats,
    AudioSamplerates,
    AudioCodecs,
    SpeechResultState,
)

SUPPORT_LANGUAGES = ["en", "de"]


async def async_get_engine(hass, config):
    """Set up Demo speech component."""
    return DemoProvider()


class DemoProvider(Provider):
    """Demo speech API provider."""

    @property
    def supported_languages(self) -> List[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_formats(self) -> List[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> List[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bitrates(self) -> List[AudioBitrates]:
        """Return a list of supported bitrates."""
        return [AudioBitrates.BITRATE_16]

    @property
    def supported_samplerates(self) -> List[AudioSamplerates]:
        """Return a list of supported samplerates."""
        return [AudioSamplerates.SAMPLERATE_16000, AudioSamplerates.SAMPLERATE_44100]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: StreamReader
    ) -> SpeechResult:
        """Process an audio stream to STT service."""

        # Read available data
        async for _ in stream.iter_chunked(4096):
            pass

        return SpeechResult("Turn the Kitchen Lights on", SpeechResultState.SUCCESS)
