"""Speech-to-Text platform for the Fish Audio integration."""

from __future__ import annotations

from collections.abc import AsyncIterable
import io
import logging
import wave

from fish_audio_sdk import Session
from fish_audio_sdk.exceptions import HttpCodeErr
from fish_audio_sdk.schemas import ASRRequest

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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FishAudioConfigEntry
from .const import DOMAIN, STT_SUPPORTED_LANGUAGES
from .entity import FishAudioEntity

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FishAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fish Audio STT platform."""
    session: Session = entry.runtime_data
    async_add_entities([FishAudioSTTEntity(entry, session)])


class FishAudioSTTEntity(FishAudioEntity, SpeechToTextEntity):
    """Fish Audio STT entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, session: Session) -> None:
        """Initialize the STT entity."""
        super().__init__(entry, session)
        self._attr_unique_id = entry.entry_id
        self._attr_name = "Speech To Text"

    @property
    def supported_languages(self) -> list[str]:
        """Return the supported languages."""
        return STT_SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return the supported audio formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return the supported audio codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return the supported audio bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return the supported audio sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return the supported audio channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream."""
        _LOGGER.debug("Processing audio stream for STT")

        # Collect raw PCM from stream
        audio_bytes = b"".join([chunk async for chunk in stream])

        if not audio_bytes or audio_bytes.strip(b"\x00") == b"":
            _LOGGER.warning("Received empty or silent audio stream for STT")
            return SpeechResult(None, SpeechResultState.ERROR)

        # Wrap PCM frames into a valid WAV container (in memory)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit samples
            wav_file.setframerate(16000)  # 16kHz sample rate
            wav_file.writeframes(audio_bytes)

        wav_bytes = wav_buffer.getvalue()

        try:
            language = metadata.language if metadata.language != "" else None

            request = ASRRequest(audio=wav_bytes, language=language)
            _LOGGER.debug("Sending %d bytes for STT", len(wav_bytes))

            response = await self.hass.async_add_executor_job(
                self._session.asr, request
            )

            _LOGGER.debug("STT response: %s", response.text)
            ir.async_delete_issue(self.hass, DOMAIN, "payment_required")
            return SpeechResult(response.text, SpeechResultState.SUCCESS)

        except HttpCodeErr as exc:
            if exc.code == 402:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "payment_required",
                    is_fixable=False,
                    severity=ir.IssueSeverity.CRITICAL,
                    translation_key="payment_required",
                )

            _LOGGER.error("API Error processing audio stream for STT: %s", str(exc))
            return SpeechResult(None, SpeechResultState.ERROR)
        except Exception:
            _LOGGER.exception("Error processing audio stream for STT")
            return SpeechResult(None, SpeechResultState.ERROR)
