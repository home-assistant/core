"""Base entity for the Speech-to-text (STT) platform."""

from abc import abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable
from contextlib import aclosing
from typing import final, override

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
)
from .models import (
    DEFAULT_AUDIO_PROCESSING,
    PartialSpeechResult,
    SpeechAudioProcessing,
    SpeechMetadata,
    SpeechResult,
)


class SpeechToTextEntity(RestoreEntity):
    """Represent a single STT provider."""

    _attr_should_poll = False
    __last_processed: str | None = None

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the state of the provider entity."""
        if self.__last_processed is None:
            return None
        return self.__last_processed

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""

    @property
    @abstractmethod
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""

    @property
    @abstractmethod
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""

    @property
    @abstractmethod
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""

    @property
    @abstractmethod
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""

    @property
    def audio_processing(self) -> SpeechAudioProcessing:
        """Return required/preferred input audio processing settings."""
        return DEFAULT_AUDIO_PROCESSING

    @callback
    def async_get_audio_processing(
        self, metadata: SpeechMetadata
    ) -> SpeechAudioProcessing:
        """Return required/preferred input audio processing settings for a request."""
        return self.audio_processing

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the provider entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_processed = state.state

    @final
    async def internal_async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service, returning only the final result."""
        async with aclosing(
            self.internal_async_process_audio_stream_with_progress(
                metadata=metadata, stream=stream
            )
        ) as results:
            async for result in results:
                if isinstance(result, SpeechResult):
                    return result

        raise RuntimeError(f"{self.entity_id} did not yield a final speech result")

    @final
    async def internal_async_process_audio_stream_with_progress(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[PartialSpeechResult | SpeechResult]:
        """Process an audio stream to STT service, yielding partial results."""
        self.__last_processed = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        # aclosing so a consumer that stops early still closes the entity's generator.
        async with aclosing(
            self.async_process_audio_stream_with_progress(
                metadata=metadata, stream=stream
            )
        ) as results:
            async for result in results:
                yield result

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        raise NotImplementedError

    async def async_process_audio_stream_with_progress(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[PartialSpeechResult | SpeechResult]:
        """Process an audio stream with an STT service, yielding partial results.

        Yield zero or more partial results followed by exactly one final
        speech result. Each partial contains the complete transcript so far for
        its speaker, and replaces the previous partial with the same speaker id.

        The default implementation falls back to async_process_audio_stream and
        yields only the final result.
        """
        yield await self.async_process_audio_stream(metadata=metadata, stream=stream)

    @callback
    def check_metadata(self, metadata: SpeechMetadata) -> bool:
        """Check if given metadata supported by this provider."""
        if (
            metadata.language not in self.supported_languages
            or metadata.format not in self.supported_formats
            or metadata.codec not in self.supported_codecs
            or metadata.bit_rate not in self.supported_bit_rates
            or metadata.sample_rate not in self.supported_sample_rates
            or metadata.channel not in self.supported_channels
        ):
            return False
        return True
