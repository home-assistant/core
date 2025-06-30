"""Support for the ElevenLabs speech-to-text service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from io import BytesIO
import logging

from elevenlabs import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import Model

from homeassistant.components import stt
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElevenLabsConfigEntry
from .const import (
    CONF_STT_AUTO_LANGUAGE,
    DEFAULT_STT_AUTO_LANGUAGE,
    DOMAIN,
    STT_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElevenLabsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ElevenLabs tts platform via config entry."""
    _LOGGER.debug("STT async_setup_entry called")
    client = config_entry.runtime_data.client
    auto_detect = config_entry.options.get(
        CONF_STT_AUTO_LANGUAGE, DEFAULT_STT_AUTO_LANGUAGE
    )

    async_add_entities(
        [
            ElevenLabsSTTEntity(
                client,
                config_entry.runtime_data.model,
                config_entry.entry_id,
                config_entry.title,
                auto_detect_language=auto_detect,
            )
        ]
    )


class ElevenLabsSTTEntity(SpeechToTextEntity):
    """The ElevenLabs STT API entity."""

    def __init__(
        self,
        client: AsyncElevenLabs,
        model: Model,
        entry_id: str,
        title: str,
        auto_detect_language: bool = False,
    ) -> None:
        """Init ElevenLabs TTS service."""
        self._client = client
        self._auto_detect_language = auto_detect_language

        # Entity attributes
        self._attr_unique_id = entry_id
        self._attr_name = f"{title} STT"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="ElevenLabs",
            model=model.name,
            entry_type=DeviceEntryType.SERVICE,
        )

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
        """Return a list of supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [
            AudioChannels.CHANNEL_MONO,
            AudioChannels.CHANNEL_STEREO,
        ]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream to STT service."""
        _LOGGER.debug(
            "Processing audio stream for STT: language=%s, format=%s, codec=%s, sample_rate=%s, channels=%s, bit_rate=%s",
            metadata.language,
            metadata.format,
            metadata.codec,
            metadata.sample_rate,
            metadata.channel,
            metadata.bit_rate,
        )

        if self._auto_detect_language:
            lang_code = None
        else:
            language = metadata.language
            if language.lower() not in [lang.lower() for lang in STT_LANGUAGES]:
                _LOGGER.warning("Unsupported language: %s", language)
                return stt.SpeechResult(None, SpeechResultState.ERROR)
            lang_code = language.split("-")[0]

        raw_pcm_compatible = (
            metadata.codec == AudioCodecs.PCM
            and metadata.sample_rate == AudioSampleRates.SAMPLERATE_16000
            and metadata.channel == AudioChannels.CHANNEL_MONO
            and metadata.bit_rate == AudioBitRates.BITRATE_16
        )
        if raw_pcm_compatible:
            file_format = "pcm_s16le_16"
        elif metadata.codec == AudioCodecs.PCM:
            _LOGGER.warning("PCM input does not meet expected raw format requirements")
            return stt.SpeechResult(None, SpeechResultState.ERROR)
        else:
            file_format = "other"

        async def read_stream_to_bytes(stream: AsyncIterable[bytes]) -> bytes:
            audio = b""
            async for chunk in stream:
                audio += chunk
            return audio

        try:
            audio = await asyncio.wait_for(read_stream_to_bytes(stream), timeout=60)
        except TimeoutError:
            _LOGGER.warning("Timeout while waiting for audio data")
            return stt.SpeechResult(None, SpeechResultState.ERROR)

        _LOGGER.debug("Finished reading audio stream, total size: %d bytes", len(audio))
        if not audio:
            _LOGGER.warning("No audio received in stream")
            return stt.SpeechResult(None, SpeechResultState.ERROR)

        lang_display = lang_code if lang_code else "auto-detected"

        _LOGGER.debug(
            "Transcribing audio (%s), format: %s, size: %d bytes",
            lang_display,
            file_format,
            len(audio),
        )

        try:
            response = await self._client.speech_to_text.convert(
                file=BytesIO(audio),
                file_format=file_format,
                model_id="scribe_v1",
                language_code=lang_code,
                diarize=False,
            )
        except ApiError as exc:
            _LOGGER.error("Error during processing of STT request: %s", exc)
            return stt.SpeechResult(None, SpeechResultState.ERROR)

        text = response.text or ""
        detected_lang_code = response.language_code or "?"
        detected_lang_prob = response.language_probability or "?"

        _LOGGER.debug(
            "Transcribed text is in language %s (probability %s): %s",
            detected_lang_code,
            detected_lang_prob,
            text,
        )

        return stt.SpeechResult(text, SpeechResultState.SUCCESS)
