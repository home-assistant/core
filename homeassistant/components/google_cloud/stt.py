"""Support for the Google Cloud STT service."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterable
import logging

from google.api_core.exceptions import GoogleAPIError, Unauthenticated
from google.cloud import speech_v1

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SERVICE_ACCOUNT_INFO,
    CONF_STT_MODEL,
    DEFAULT_STT_MODEL,
    DOMAIN,
    STT_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Cloud speech platform via config entry."""
    service_account_info = config_entry.data[CONF_SERVICE_ACCOUNT_INFO]
    client = speech_v1.SpeechAsyncClient.from_service_account_info(service_account_info)
    async_add_entities([GoogleCloudSpeechToTextEntity(config_entry, client)])


class GoogleCloudSpeechToTextEntity(SpeechToTextEntity):
    """Google Cloud STT entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: speech_v1.SpeechAsyncClient,
    ) -> None:
        """Init Google Cloud STT entity."""
        self._attr_unique_id = f"{entry.entry_id}-stt"
        self._attr_name = entry.title
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Google",
            model="Cloud",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self._entry = entry
        self._client = client
        self._model = entry.options.get(CONF_STT_MODEL, DEFAULT_STT_MODEL)

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
        streaming_config = speech_v1.StreamingRecognitionConfig(
            config=speech_v1.RecognitionConfig(
                encoding=(
                    speech_v1.RecognitionConfig.AudioEncoding.OGG_OPUS
                    if metadata.codec == AudioCodecs.OPUS
                    else speech_v1.RecognitionConfig.AudioEncoding.LINEAR16
                ),
                sample_rate_hertz=metadata.sample_rate,
                language_code=metadata.language,
                model=self._model,
            )
        )

        async def request_generator() -> (
            AsyncGenerator[speech_v1.StreamingRecognizeRequest]
        ):
            # The first request must only contain a streaming_config
            yield speech_v1.StreamingRecognizeRequest(streaming_config=streaming_config)
            # All subsequent requests must only contain audio_content
            async for audio_content in stream:
                yield speech_v1.StreamingRecognizeRequest(audio_content=audio_content)

        try:
            responses = await self._client.streaming_recognize(
                requests=request_generator(),
                timeout=10,
            )

            transcript = ""
            async for response in responses:
                _LOGGER.debug("response: %s", response)
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript += response.results[0].alternatives[0].transcript
        except GoogleAPIError as err:
            _LOGGER.error("Error occurred during Google Cloud STT call: %s", err)
            if isinstance(err, Unauthenticated):
                self._entry.async_start_reauth(self.hass)
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult(transcript, SpeechResultState.SUCCESS)
