"""Support for Wyoming speech to text services."""
from collections.abc import AsyncIterable
import logging

from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.info import Info

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, SAMPLE_CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH
from .error import WyomingError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wyoming speech to text."""
    wyoming_info = hass.data[DOMAIN][config_entry.entry_id]["info"]
    hass.data[DOMAIN][config_entry.entry_id]["provider"] = WyomingSttProvider(
        hass,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        wyoming_info,
    )

    await async_load_platform(
        hass, Platform.STT, DOMAIN, {"entry_id": config_entry.entry_id}, {}
    )


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> stt.Provider:
    """Set up Wyoming speech to text component."""
    if discovery_info is None:
        raise ValueError("Missing discovery info")

    entry_id = discovery_info["entry_id"]

    return hass.data[DOMAIN][entry_id]["provider"]


class WyomingSttProvider(stt.Provider):
    """Wyoming speech to text provider."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, wyoming_info: Info
    ) -> None:
        """Set up provider."""
        self.hass = hass
        self.host = host
        self.port = port
        self.wyoming_info = wyoming_info

        # Set supported languages
        model_languages: set[str] = set()
        for asr_program in wyoming_info.asr:
            if not asr_program.installed:
                continue

            for asr_model in asr_program.models:
                if not asr_model.installed:
                    continue

                model_languages.update(asr_model.languages)

        self._supported_languages = list(model_languages)

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
