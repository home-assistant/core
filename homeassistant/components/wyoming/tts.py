"""Support for Wyoming text-to-speech services."""
from collections import defaultdict
import io
import logging
import wave

from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize, SynthesizeVoice

from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SPEAKER, DOMAIN
from .data import WyomingService
from .error import WyomingError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wyoming speech-to-text."""
    service: WyomingService = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            WyomingTtsProvider(config_entry, service),
        ]
    )


class WyomingTtsProvider(tts.TextToSpeechEntity):
    """Wyoming text-to-speech provider."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        service: WyomingService,
    ) -> None:
        """Set up provider."""
        self.service = service
        self._tts_service = next(tts for tts in service.info.tts if tts.installed)

        voice_languages: set[str] = set()
        self._voices: dict[str, list[tts.Voice]] = defaultdict(list)
        for voice in self._tts_service.voices:
            if not voice.installed:
                continue

            voice_languages.update(voice.languages)
            for language in voice.languages:
                self._voices[language].append(
                    tts.Voice(
                        voice_id=voice.name,
                        name=voice.description or voice.name,
                    )
                )

        # Sort voices by name
        for language in self._voices:
            self._voices[language] = sorted(
                self._voices[language], key=lambda v: v.name
            )

        self._supported_languages: list[str] = list(voice_languages)

        self._attr_name = self._tts_service.name
        self._attr_unique_id = f"{config_entry.entry_id}-tts"

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
        return [tts.ATTR_AUDIO_OUTPUT, tts.ATTR_VOICE, ATTR_SPEAKER]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {tts.ATTR_AUDIO_OUTPUT: "wav"}

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Return a list of supported voices for a language."""
        return self._voices.get(language)

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from TCP socket."""
        voice_name: str | None = options.get(tts.ATTR_VOICE)
        voice_speaker: str | None = options.get(ATTR_SPEAKER)

        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                voice: SynthesizeVoice | None = None
                if voice_name is not None:
                    voice = SynthesizeVoice(name=voice_name, speaker=voice_speaker)

                synthesize = Synthesize(text=message, voice=voice)
                await client.write_event(synthesize.event())

                with io.BytesIO() as wav_io:
                    wav_writer: wave.Wave_write | None = None
                    while True:
                        event = await client.read_event()
                        if event is None:
                            _LOGGER.debug("Connection lost")
                            return (None, None)

                        if AudioStop.is_type(event.type):
                            break

                        if AudioChunk.is_type(event.type):
                            chunk = AudioChunk.from_event(event)
                            if wav_writer is None:
                                wav_writer = wave.open(wav_io, "wb")
                                wav_writer.setframerate(chunk.rate)
                                wav_writer.setsampwidth(chunk.width)
                                wav_writer.setnchannels(chunk.channels)

                            wav_writer.writeframes(chunk.audio)

                    if wav_writer is not None:
                        wav_writer.close()

                    data = wav_io.getvalue()

        except (OSError, WyomingError):
            return (None, None)

        if options[tts.ATTR_AUDIO_OUTPUT] == "wav":
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
