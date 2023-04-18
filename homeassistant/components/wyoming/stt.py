"""Support for Wyoming speech to text services."""
from collections.abc import AsyncIterable
import logging

from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import SAMPLE_CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH
from .error import WyomingError
from .info import load_wyoming_info

_LOGGER = logging.getLogger(__name__)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> stt.Provider:
    """Set up Wyoming speech to text component."""
    if discovery_info is None:
        raise ValueError("Missing discovery info")

    address = discovery_info["address"]
    host, port_str = address.split(":", maxsplit=1)
    port = int(port_str)

    provider = WyomingSttProvider(hass, host, port)
    hass.async_create_background_task(
        provider.load_info(),
        "stt-wyoming-info",
    )

    return provider


class WyomingSttProvider(stt.Provider):
    """Wyoming speech to text provider."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up provider."""
        self.hass = hass
        self.host = host
        self.port = port
        self._supported_languages: list[str] = []

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
            async with AsyncTcpClient(self.host, self.port) as client:
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

                await client.write_event(AudioStop().event())

                while True:
                    event = await client.read_event()
                    if event is None:
                        raise WyomingError("Connection closed unexpectedly")

                    if Transcript.is_type(event.type):
                        transcript = Transcript.from_event(event)
                        text = transcript.text
                        break

        except (OSError, WyomingError):
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        return stt.SpeechResult(
            text,
            stt.SpeechResultState.SUCCESS,
        )

    async def load_info(self):
        """Gather set of all supported languages from models."""
        wyoming_info = await load_wyoming_info(self.host, self.port)
        if wyoming_info is None:
            return

        model_languages: set[str] = set()
        for asr_program in wyoming_info.asr:
            if not asr_program.installed:
                continue

            for asr_model in asr_program.models:
                if not asr_model.installed:
                    continue

                model_languages.update(asr_model.languages)

        self._supported_languages = list(model_languages)
        _LOGGER.debug(
            "Supported languages: %s",
            self._supported_languages,
        )
