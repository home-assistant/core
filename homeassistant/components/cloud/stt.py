"""Support for the cloud for speech to text service."""
from __future__ import annotations

import asyncio
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
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .assist_pipeline import async_migrate_cloud_pipeline_engine
from .client import CloudClient
from .const import DATA_PLATFORMS_SETUP, DOMAIN, STT_ENTITY_UNIQUE_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud speech platform via config entry."""
    stt_platform_loaded: asyncio.Event = hass.data[DATA_PLATFORMS_SETUP][Platform.STT]
    stt_platform_loaded.set()
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]
    async_add_entities([CloudProviderEntity(cloud)])


class CloudProviderEntity(SpeechToTextEntity):
    """Home Assistant Cloud speech API provider."""

    _attr_name = "Home Assistant Cloud"
    _attr_unique_id = STT_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize cloud Speech to text entity."""
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

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await async_migrate_cloud_pipeline_engine(
            self.hass, platform=Platform.STT, engine_id=self.entity_id
        )

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
