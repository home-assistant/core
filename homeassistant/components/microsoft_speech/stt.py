"""Support for the Microsoft Azure Speech-to-Text service."""

from __future__ import annotations

from collections.abc import AsyncIterable
import logging

import azure.cognitiveservices.speech as speechsdk

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

from .const import DATA_SPEECH_CONFIG, DOMAIN, SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Microsoft Speech To Text platform via config entry."""
    async_add_entities([MicrosoftSpeechToTextEntity(config_entry)])


class MicrosoftSpeechToTextEntity(SpeechToTextEntity):
    """Microsoft Speech To Text."""

    def __init__(
        self,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Microsoft Azure STT entity."""
        self._attr_unique_id = f"{entry.entry_id}"
        self._attr_name = entry.title
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Microsoft",
            model="Azure Speech Services",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self._entry = entry
        self._speech_config = entry.runtime_data[DATA_SPEECH_CONFIG]

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [
            AudioSampleRates.SAMPLERATE_8000,
            AudioSampleRates.SAMPLERATE_16000,
            AudioSampleRates.SAMPLERATE_32000,
            AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO, AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""

        self._speech_config.speech_recognition_language = metadata.language

        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=metadata.sample_rate.value,
            bits_per_sample=metadata.bit_rate.value,
            channels=metadata.channel.value,
        )

        push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._speech_config, audio_config=audio_config
        )

        try:
            total_bytes = 0
            async for chunk in stream:
                if chunk:
                    push_stream.write(chunk)
                    total_bytes += len(chunk)

            push_stream.close()

            result_future = speech_recognizer.recognize_once_async()
            result = await self.hass.async_add_executor_job(result_future.get)
        except Exception:
            _LOGGER.exception("Exception during speech recognition")
            return SpeechResult(None, SpeechResultState.ERROR)

        _LOGGER.debug("Recognition result: %s", result)
        _LOGGER.debug("Endpoint id: %s", speech_recognizer.endpoint_id)

        match result.reason:
            case speechsdk.ResultReason.RecognizedSpeech:
                _LOGGER.debug("Recognized speech: %s", result.text)
                return SpeechResult(result.text, SpeechResultState.SUCCESS)
            case speechsdk.ResultReason.NoMatch:
                _LOGGER.debug("Speech could not be recognized")
                return SpeechResult(None, SpeechResultState.ERROR)
            case speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                _LOGGER.debug(
                    "Speech Recognition canceled: %s", cancellation_details.reason
                )
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    _LOGGER.error(
                        "Error details: %s", cancellation_details.error_details
                    )
                return SpeechResult(None, SpeechResultState.ERROR)
            case _:
                _LOGGER.debug("Unhandled result reason: %s", result.reason)

        return SpeechResult("", SpeechResultState.ERROR)
