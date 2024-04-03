"""Support for Wyoming speech-to-text services."""

from collections.abc import AsyncIterable
import logging

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SAMPLE_CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH
from .data import WyomingService
from .error import WyomingError
from .models import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wyoming speech-to-text."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            WyomingSttProvider(config_entry, item.service),
        ]
    )


class WyomingSttProvider(stt.SpeechToTextEntity):
    """Wyoming speech-to-text provider."""

    def __init__(
        self,
        config_entry: ConfigEntry,
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
        self._attr_name = asr_service.name
        self._attr_unique_id = f"{config_entry.entry_id}-stt"

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bitrates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

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

                async for audio_bytes in stream:
                    chunk = AudioChunk(
                        rate=SAMPLE_RATE,
                        width=SAMPLE_WIDTH,
                        channels=SAMPLE_CHANNELS,
                        audio=audio_bytes,
                    )
                    await client.write_event(chunk.event())

                # End audio stream
                await client.write_event(AudioStop().event())

                while True:
                    event = await client.read_event()
                    if event is None:
                        _LOGGER.debug("Connection lost")
                        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

                    if Transcript.is_type(event.type):
                        transcript = Transcript.from_event(event)
                        text = transcript.text
                        break

        except (OSError, WyomingError):
            _LOGGER.exception("Error processing audio stream")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        return stt.SpeechResult(
            text,
            stt.SpeechResultState.SUCCESS,
        )
