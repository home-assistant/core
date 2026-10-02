"""Support for Wyoming speech-to-text services."""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
import logging
from typing import Protocol, override, runtime_checkable

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SAMPLE_CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH
from .data import WyomingService
from .error import WyomingError, error_event_message
from .models import WyomingConfigEntry

_LOGGER = logging.getLogger(__name__)


@runtime_checkable
class _ClosableAsyncIterator(Protocol):
    """Async iterator that can be closed."""

    async def aclose(self) -> None:
        """Close the iterator."""


async def _async_upload_audio(
    client: AsyncTcpClient, stream: AsyncIterable[bytes]
) -> None:
    """Upload an audio stream to a Wyoming service."""
    stream_iterator: AsyncIterator[bytes] = aiter(stream)
    try:
        async for audio_bytes in stream_iterator:
            chunk = AudioChunk(
                rate=SAMPLE_RATE,
                width=SAMPLE_WIDTH,
                channels=SAMPLE_CHANNELS,
                audio=audio_bytes,
            )
            await client.write_event(chunk.event())

        await client.write_event(AudioStop().event())
    finally:
        if isinstance(stream_iterator, _ClosableAsyncIterator):
            await stream_iterator.aclose()


async def _async_receive_result(client: AsyncTcpClient) -> stt.SpeechResult:
    """Receive a transcription result from a Wyoming service."""
    while True:
        event = await client.read_event()
        if event is None:
            _LOGGER.debug("Connection lost")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        if Error.is_type(event.type):
            _LOGGER.error(error_event_message(Error.from_event(event)))
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        if Transcript.is_type(event.type):
            transcript = Transcript.from_event(event)
            return stt.SpeechResult(
                transcript.text,
                stt.SpeechResultState.SUCCESS,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming speech-to-text."""
    item = config_entry.runtime_data
    async_add_entities(
        [
            WyomingSttProvider(config_entry, item.service),
        ]
    )


class WyomingSttProvider(stt.SpeechToTextEntity):
    """Wyoming speech-to-text provider."""

    def __init__(
        self,
        config_entry: WyomingConfigEntry,
        service: WyomingService,
    ) -> None:
        """Set up provider."""
        self.service = service
        asr_service = service.info.asr[0]

        model_languages: set[str] = set()
        for asr_model in asr_service.models:
            if asr_model.installed:
                model_languages.update(asr_model.languages)

        self._supported_languages = list(model_languages)
        self._audio_processing = stt.SpeechAudioProcessing(
            requires_external_vad=asr_service.requires_external_vad,
            prefers_auto_gain_enabled=asr_service.prefers_auto_gain_enabled,
            prefers_noise_reduction_enabled=asr_service.prefers_noise_reduction_enabled,
        )
        self._attr_name = asr_service.name
        self._attr_unique_id = f"{config_entry.entry_id}-stt"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

    @property
    @override
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    @override
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    @override
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bitrates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    @property
    @override
    def audio_processing(self) -> stt.SpeechAudioProcessing:
        """Return required/preferred input audio processing settings."""
        return self._audio_processing

    @override
    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream to STT service."""
        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                # Set transcription language
                await client.write_event(Transcribe(language=metadata.language).event())

                # Begin audio stream
                await client.write_event(
                    AudioStart(
                        rate=SAMPLE_RATE,
                        width=SAMPLE_WIDTH,
                        channels=SAMPLE_CHANNELS,
                    ).event(),
                )

                upload_task = asyncio.create_task(_async_upload_audio(client, stream))
                receive_task = asyncio.create_task(_async_receive_result(client))
                tasks = (upload_task, receive_task)
                try:
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )

                    if receive_task in done:
                        return receive_task.result()

                    upload_task.result()
                    return await receive_task
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                    await asyncio.gather(*tasks, return_exceptions=True)

        except OSError, WyomingError:
            _LOGGER.exception("Error processing audio stream")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
