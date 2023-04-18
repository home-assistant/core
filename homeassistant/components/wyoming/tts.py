"""Support for Wyoming text to speech services."""
import io
import logging
import wave

from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize

from homeassistant.components import tts
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .error import WyomingError
from .info import load_wyoming_info

_LOGGER = logging.getLogger(__name__)


async def async_get_engine(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> tts.Provider:
    """Set up Wyoming text to speech component."""
    if discovery_info is None:
        raise ValueError("Missing discovery info")

    address = discovery_info["address"]
    host, port_str = address.split(":", maxsplit=1)
    port = int(port_str)

    provider = WyomingTtsProvider(hass, host, port)
    hass.async_create_background_task(
        provider.load_info(),
        "tts-wyoming-info",
    )

    return provider


class WyomingTtsProvider(tts.Provider):
    """Wyoming text to speech provider."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Set up provider."""
        self.hass = hass
        self.host = host
        self.port = port
        self.name = "Wyoming"
        self._supported_languages: list[str] = []

    @property
    def default_language(self):
        """Return default language."""
        if not self._supported_languages:
            return None

        return self._supported_languages[0]

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return self._supported_languages

    @property
    def supported_options(self):
        """Return list of supported options like voice, emotion."""
        return [tts.ATTR_AUDIO_OUTPUT]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {tts.ATTR_AUDIO_OUTPUT: "wav"}

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from UNIX socket."""
        try:
            async with AsyncTcpClient(self.host, self.port) as client:
                await client.write_event(Synthesize(message).event())

                with io.BytesIO() as wav_io:
                    wav_writer: wave.Wave_write = wave.open(wav_io, "wb")
                    with wav_writer:
                        is_first_chunk = True

                        while True:
                            event = await client.read_event()
                            if event is None:
                                raise WyomingError("Connection closed unexpectedly")

                            if AudioStop.is_type(event.type):
                                break

                            if AudioChunk.is_type(event.type):
                                chunk = AudioChunk.from_event(event)
                                if is_first_chunk:
                                    wav_writer.setframerate(chunk.rate)
                                    wav_writer.setsampwidth(chunk.width)
                                    wav_writer.setnchannels(chunk.channels)
                                    is_first_chunk = False

                                wav_writer.writeframes(chunk.audio)

                    data = wav_io.getvalue()

        except (OSError, WyomingError):
            return (None, None)

        if (options is None) or (options[tts.ATTR_AUDIO_OUTPUT] == "wav"):
            return ("wav", data)

        # Raw output (convert to 16Khz, 16-bit mono)
        with io.BytesIO(data) as wav_io:
            wav_reader: wave.Wave_read = wave.open(wav_io, "rb")
            raw_data = (
                AudioChunkConverter(
                    rate=16000,
                    width=2,
                    channels=1,
                )
                .convert(
                    AudioChunk(
                        audio=wav_reader.readframes(wav_reader.getnframes()),
                        rate=wav_reader.getframerate(),
                        width=wav_reader.getsampwidth(),
                        channels=wav_reader.getnchannels(),
                    )
                )
                .audio
            )

        return ("raw", raw_data)

    async def load_info(self):
        """Gather set of all supported languages from voices."""
        wyoming_info = await load_wyoming_info(self.host, self.port)
        if wyoming_info is None:
            return

        voice_languages: set[str] = set()
        for tts_program in wyoming_info.tts:
            if not tts_program.installed:
                continue

            for voice in tts_program.voices:
                if not voice.installed:
                    continue

                voice_languages.update(voice.languages)

        self._supported_languages = list(voice_languages)
        _LOGGER.debug(
            "Supported languages: %s",
            self._supported_languages,
        )
