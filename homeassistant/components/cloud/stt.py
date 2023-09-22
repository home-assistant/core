"""Support for the cloud for speech to text service."""
from __future__ import annotations

from collections.abc import AsyncIterable
import logging

from hass_nabucasa import Cloud
from hass_nabucasa.voice import STT_LANGUAGES, VoiceError

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

from .client import CloudClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CloudProvider:
    """Set up Cloud speech component."""
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]

    cloud_provider = CloudProvider(cloud)
    if discovery_info is not None:
        discovery_info["platform_loaded"].set()
    return cloud_provider


class CloudProvider(Provider):
    """NabuCasa speech API provider."""

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Home Assistant NabuCasa Speech to text."""
        self.cloud = cloud

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return STT_LANGUAGES

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
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        content_type = (
            f"audio/{metadata.format!s}; codecs=audio/{metadata.codec!s};"
            " samplerate=16000"
        )

        # Process STT
        try:
            result = await self.cloud.voice.process_stt(
                stream=stream,
                content_type=content_type,
                language=metadata.language,
            )
        except VoiceError as err:
            _LOGGER.error("Voice error: %s", err)
            return SpeechResult(None, SpeechResultState.ERROR)

        # Return Speech as Text
        return SpeechResult(
            result.text,
            SpeechResultState.SUCCESS if result.success else SpeechResultState.ERROR,
        )
