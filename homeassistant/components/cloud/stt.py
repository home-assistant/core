"""Support for the cloud for speech to text service."""

from collections.abc import AsyncIterable
import logging
from typing import override

from hass_nabucasa import Cloud, SpeechToTextV2Error
from hass_nabucasa.voice import STT_LANGUAGES, STTResponse, VoiceError

from homeassistant.components import labs
from homeassistant.components.stt import (
    DEFAULT_AUDIO_PROCESSING,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechAudioProcessing,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_when_setup

from .assist_pipeline import async_migrate_cloud_pipeline_engine
from .client import CloudClient
from .const import (
    DATA_CLOUD,
    DATA_PLATFORMS_SETUP,
    DOMAIN,
    PREVIEW_FEATURE_STT_V2,
    STT_ENTITY_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)

# STT v2 detects the end of speech itself and works best on untouched audio.
STT_V2_AUDIO_PROCESSING = SpeechAudioProcessing(
    requires_external_vad=True,
    prefers_auto_gain_enabled=False,
    prefers_noise_reduction_enabled=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud speech platform via config entry."""
    stt_platform_loaded = hass.data[DATA_PLATFORMS_SETUP][Platform.STT]
    stt_platform_loaded.set()
    cloud = hass.data[DATA_CLOUD]
    async_add_entities([CloudProviderEntity(cloud)])


class CloudProviderEntity(SpeechToTextEntity):
    """Home Assistant Cloud speech API provider."""

    _attr_name = "Home Assistant Cloud"
    _attr_unique_id = STT_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize cloud Speech to text entity."""
        self.cloud = cloud

    @property
    def _stt_v2_enabled(self) -> bool:
        """Return if the v2 speech to text service is enabled."""
        return labs.async_is_preview_feature_enabled(
            self.hass, DOMAIN, PREVIEW_FEATURE_STT_V2
        )

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return STT_LANGUAGES

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
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    @property
    @override
    def audio_processing(self) -> SpeechAudioProcessing:
        """Return required/preferred input audio processing settings."""
        if self._stt_v2_enabled:
            return STT_V2_AUDIO_PROCESSING
        return DEFAULT_AUDIO_PROCESSING

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""

        async def pipeline_setup(hass: HomeAssistant, _comp: str) -> None:
            """When assist_pipeline is set up."""
            assert self.platform.config_entry
            self.platform.config_entry.async_create_task(
                hass,
                async_migrate_cloud_pipeline_engine(
                    self.hass, platform=Platform.STT, engine_id=self.entity_id
                ),
            )

        async_when_setup(self.hass, "assist_pipeline", pipeline_setup)

        self.async_on_remove(
            labs.async_subscribe_preview_feature(
                self.hass,
                DOMAIN,
                PREVIEW_FEATURE_STT_V2,
                self._async_handle_labs_update,
            )
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Close the connection when the entity is removed."""
        await self.cloud.stt_v2.disconnect()

    async def _async_handle_labs_update(
        self, event_data: labs.EventLabsUpdatedData
    ) -> None:
        """Close the connection to the v2 service when it is turned off."""
        if not event_data["enabled"]:
            await self.cloud.stt_v2.disconnect()

    @override
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        # STT v2 covers fewer languages, so fall back for the rest.
        use_stt_v2 = self._stt_v2_enabled and bool(
            self.cloud.stt_v2.resolve_language(metadata.language)
        )

        try:
            if use_stt_v2:
                result = await self._async_process_stt_v2(metadata, stream)
            else:
                result = await self._async_process_azure_stt(metadata, stream)
        except (SpeechToTextV2Error, VoiceError) as err:
            _LOGGER.error("Voice error: %s", err)
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult(
            result.text,
            SpeechResultState.SUCCESS if result.success else SpeechResultState.ERROR,
        )

    async def _async_process_stt_v2(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> STTResponse:
        """Process an audio stream with the v2 speech to text service."""
        return await self.cloud.stt_v2.process_stt(
            stream=stream,
            language=metadata.language,
            audio_format=metadata.format.value,
            codec=metadata.codec.value,
            bit_rate=metadata.bit_rate.value,
            sample_rate=metadata.sample_rate.value,
            channel=metadata.channel.value,
        )

    async def _async_process_azure_stt(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> STTResponse:
        """Process an audio stream with the Azure speech to text service."""
        content_type = (
            f"audio/{metadata.format!s}; codecs=audio/{metadata.codec!s};"
            " samplerate=16000"
        )
        return await self.cloud.voice.process_stt(
            stream=stream,
            content_type=content_type,
            language=metadata.language,
        )
