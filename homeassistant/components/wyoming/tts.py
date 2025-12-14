"""Support for Wyoming text-to-speech services."""

from collections import defaultdict
from collections.abc import AsyncGenerator
import io
import logging
import wave

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeVoice,
)

from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_SPEAKER, DOMAIN
from .data import WyomingService
from .error import WyomingError
from .models import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming speech-to-text."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            WyomingTtsProvider(config_entry, item.service),
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
        self.config_entry = config_entry
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
        return [
            tts.ATTR_AUDIO_OUTPUT,
            tts.ATTR_VOICE,
            ATTR_SPEAKER,
        ]

    @property
    def default_options(self):
        """Return a dict include default options."""
        return {}

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

        return ("wav", data)

    def async_supports_streaming_input(self) -> bool:
        """Return if the TTS engine supports streaming input."""
        return self._tts_service.supports_synthesize_streaming

    async def async_stream_tts_audio(
        self, request: tts.TTSAudioRequest
    ) -> tts.TTSAudioResponse:
        """Generate speech from an incoming message."""
        voice_name: str | None = request.options.get(tts.ATTR_VOICE)
        voice_speaker: str | None = request.options.get(ATTR_SPEAKER)
        voice: SynthesizeVoice | None = None
        if voice_name is not None:
            voice = SynthesizeVoice(name=voice_name, speaker=voice_speaker)

        client = AsyncTcpClient(self.service.host, self.service.port)
        await client.connect()

        # Stream text chunks to client
        self.config_entry.async_create_background_task(
            self.hass,
            self._write_tts_message(request.message_gen, client, voice),
            "wyoming tts write",
        )

        async def data_gen():
            # Stream audio bytes from client
            try:
                async for data_chunk in self._read_tts_audio(client):
                    yield data_chunk
            finally:
                await client.disconnect()

        return tts.TTSAudioResponse("wav", data_gen())

    async def _write_tts_message(
        self,
        message_gen: AsyncGenerator[str],
        client: AsyncTcpClient,
        voice: SynthesizeVoice | None,
    ) -> None:
        """Write text chunks to the client."""
        try:
            # Start stream
            await client.write_event(SynthesizeStart(voice=voice).event())

            # Accumulate entire message for synthesize event.
            message = ""
            async for message_chunk in message_gen:
                message += message_chunk

                await client.write_event(SynthesizeChunk(text=message_chunk).event())

            # Send entire message for backwards compatibility
            await client.write_event(Synthesize(text=message, voice=voice).event())

            # End stream
            await client.write_event(SynthesizeStop().event())
        except (OSError, WyomingError):
            # Disconnected
            _LOGGER.warning("Unexpected disconnection from TTS client")

    async def _read_tts_audio(self, client: AsyncTcpClient) -> AsyncGenerator[bytes]:
        """Read audio events from the client and yield WAV audio chunks.

        The WAV header is sent first with a frame count of 0 to indicate that
        we're streaming and don't know the number of frames ahead of time.
        """
        wav_header_sent = False

        try:
            while event := await client.read_event():
                if wav_header_sent and AudioChunk.is_type(event.type):
                    # PCM audio
                    yield AudioChunk.from_event(event).audio
                elif (not wav_header_sent) and AudioStart.is_type(event.type):
                    # WAV header with nframes = 0 for streaming
                    audio_start = AudioStart.from_event(event)
                    with io.BytesIO() as wav_io:
                        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
                        with wav_file:
                            wav_file.setframerate(audio_start.rate)
                            wav_file.setsampwidth(audio_start.width)
                            wav_file.setnchannels(audio_start.channels)

                        wav_io.seek(0)
                        yield wav_io.getvalue()

                    wav_header_sent = True
                elif SynthesizeStopped.is_type(event.type):
                    # All TTS audio has been received
                    break
        except (OSError, WyomingError):
            # Disconnected
            _LOGGER.warning("Unexpected disconnection from TTS client")
