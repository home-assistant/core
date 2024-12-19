"""Support for the Microsoft Speech-to-Text service."""

from __future__ import annotations

from collections.abc import AsyncIterable
import logging

import aiohttp

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

from .const import DOMAIN, STT_ENDPOINT, SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Microsoft Speech To Text platform via config entry."""
    async_add_entities([MicrosoftSpeechToTextEntity(config_entry)])


class MicrosoftSpeechToTextEntity(SpeechToTextEntity):
    """Microsoft Speech To Text using REST API."""

    def __init__(
        self,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Microsoft Speech To Text entity."""
        self._attr_unique_id = f"{entry.entry_id}"
        self._attr_name = entry.title
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Microsoft",
            model="Azure Speech Service",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        # self._entry = entry
        self._speech_config = entry.data

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
        """Process an audio stream to STT service via REST API."""

        api_key = self._speech_config.get("api_key")
        if api_key is None:
            _LOGGER.error("API key is missing in configuration")
            return SpeechResult(None, SpeechResultState.ERROR)

        region = self._speech_config.get("region")
        stt_endpoint = STT_ENDPOINT.format(region=region)
        language = metadata.language

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": f"audio/wav; codec=audio/pcm; samplerate={metadata.sample_rate.value}",
            "Accept": "application/json",
        }

        params = {
            "language": language,
        }

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    stt_endpoint,
                    headers=headers,
                    params=params,
                    data=self._audio_stream_generator(stream),
                ) as response,
            ):
                if response.status == 200:
                    response_json = await response.json()
                    _LOGGER.debug("STT API Response: %s", response_json)
                    if response_json.get("DisplayText"):
                        return SpeechResult(
                            response_json["DisplayText"], SpeechResultState.SUCCESS
                        )
                    _LOGGER.debug("No speech was recognized")
                    return SpeechResult(None, SpeechResultState.ERROR)
                if response.status == 400:
                    _LOGGER.error("Bad request: %s", response.reason)
                elif response.status == 401:
                    _LOGGER.error("Unauthorized: %s", response.reason)
                elif response.status == 429:
                    _LOGGER.error("Too many requests: %s", response.reason)
                elif response.status == 502:
                    _LOGGER.error("Bad gateway: %s", response.reason)
                else:
                    _LOGGER.error(
                        "Failed to connect to Microsoft Speech API: %s",
                        response.reason,
                    )
                return SpeechResult(None, SpeechResultState.ERROR)
        except aiohttp.ClientError:
            _LOGGER.error("Connection error while processing audio stream")
            return SpeechResult(None, SpeechResultState.ERROR)
        except Exception:
            _LOGGER.exception("Unexpected error during speech recognition")
            return SpeechResult(None, SpeechResultState.ERROR)

    async def _audio_stream_generator(
        self, stream: AsyncIterable[bytes]
    ) -> AsyncIterable[bytes]:
        """Generate stream audio chunks."""
        async for chunk in stream:
            if chunk:
                yield chunk
