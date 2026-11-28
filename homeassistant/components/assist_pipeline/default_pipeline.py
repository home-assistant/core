"""Default implementation of the Assist pipeline engine."""

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import audioop  # pylint: disable=deprecated-module
import hass_nabucasa

from homeassistant.components import (
    conversation,
    media_player,
    stt,
    tts,
    voice_support,
    wake_word,
)
from homeassistant.components.tts import TextToSpeechCommonOption
from homeassistant.const import MATCH_ALL, EntityStateAttribute
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import (
    chat_session,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.util import language as language_util
from homeassistant.util.hass_dict import HassKey

from .audio_enhancer import AudioEnhancer, EnhancedAudioChunk, MicroVadSpeexEnhancer
from .const import (
    ACKNOWLEDGE_PATH,
    BYTES_PER_CHUNK,
    MS_PER_CHUNK,
    SAMPLE_CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    SAMPLES_PER_CHUNK,
)
from .error import (
    IntentRecognitionError,
    PipelineRunValidationError,
    SpeechToTextError,
    TextToSpeechError,
    WakeWordDetectionAborted,
    WakeWordDetectionError,
    WakeWordTimeoutError,
)
from .models import (
    PIPELINE_STAGE_ORDER,
    AudioSettings,
    Pipeline,
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
    WakeWordSettings,
)
from .vad import AudioBuffer, VoiceActivityTimeout, VoiceCommandSegmenter, chunk_samples

if TYPE_CHECKING:
    from hassil.recognize import RecognizeResult

    from .run import _PipelineProcessorRequest

_LOGGER = logging.getLogger(__name__)

KEY_PIPELINE_CONVERSATION_DATA: HassKey[dict[str, PipelineConversationData]] = HassKey(
    "pipeline_conversation_data"
)
STREAM_RESPONSE_CHARS = 60
RUN_COMMAND_TIMEOUT_MS = 15_000
"""The segmenter's cap, kept while a run says where the command ends."""


async def _skip_audio(
    audio_stream: AsyncIterable[bytes], num_bytes: int
) -> AsyncGenerator[bytes]:
    """Yield the audio after the first num_bytes."""
    async for chunk in audio_stream:
        if num_bytes > 0:
            skipped = min(num_bytes, len(chunk))
            chunk = chunk[skipped:]
            num_bytes -= skipped
        if chunk:
            yield chunk


async def _async_until[T](
    stream: AsyncIterable[T], stop: asyncio.Event
) -> AsyncGenerator[T]:
    """Yield from the stream until it ends or stop is set, also while it waits."""
    items = aiter(stream)
    stopped = asyncio.ensure_future(stop.wait())
    next_item: asyncio.Future[T | None] | None = None
    try:
        while True:
            next_item = asyncio.ensure_future(anext(items, None))
            await asyncio.wait(
                (next_item, stopped), return_when=asyncio.FIRST_COMPLETED
            )
            if stopped.done():
                return
            if (item := next_item.result()) is None:
                return
            yield item
    finally:
        stopped.cancel()
        if (next_item is not None) and (not next_item.done()):
            next_item.cancel()
            await asyncio.wait((next_item,))
        # A source that already gave its next item waits at a yield, holding
        # what it opened
        if isinstance(items, AsyncGenerator):
            await items.aclose()


@callback
def _async_local_fallback_intent_filter(result: RecognizeResult) -> bool:
    """Filter out intents that are not local fallback."""
    return result.intent.name in (
        intent.INTENT_GET_STATE,
        media_player.INTENT_MEDIA_SEARCH_AND_PLAY,
    )


@callback
def async_resolve_stt_engine_language(
    hass: HomeAssistant, language: str, engine_id: str | None = None
) -> tuple[str, str] | None:
    """Return an STT engine, the default one if not given, and its language."""
    if engine_id is None and (engine_id := stt.async_default_engine(hass)) is None:
        return None
    if (engine := stt.async_get_speech_to_text_engine(hass, engine_id)) is None:
        return None

    if languages := language_util.matches(
        language, engine.supported_languages, country=hass.config.country
    ):
        return (engine_id, languages[0])

    _LOGGER.debug(
        "Speech-to-text engine '%s' does not support language '%s'",
        engine_id,
        language,
    )
    return None


@callback
def async_resolve_tts_engine_language_voice(
    hass: HomeAssistant, language: str, engine_id: str | None = None
) -> tuple[str, str, str | None] | None:
    """Return a TTS engine, the default one if not given, its language and voice."""
    if engine_id is None and (engine_id := tts.async_default_engine(hass)) is None:
        return None
    if (engine := tts.get_engine_instance(hass, engine_id)) is None:
        return None

    if languages := language_util.matches(
        language, engine.supported_languages, country=hass.config.country
    ):
        voices = engine.async_get_supported_voices(languages[0])
        return (engine_id, languages[0], voices[0].voice_id if voices else None)

    _LOGGER.debug(
        "Text-to-speech engine '%s' does not support language '%s'",
        engine_id,
        language,
    )
    return None


class _PipelineController(Protocol):
    """Home Assistant services exposed to a pipeline processor."""

    @property
    def hass(self) -> HomeAssistant:
        """Return the Home Assistant instance."""

    @property
    def context(self) -> Context:
        """Return the run context."""

    @property
    def pipeline(self) -> Pipeline:
        """Return the pipeline configuration."""

    @property
    def start_stage(self) -> PipelineStage:
        """Return the first stage to process."""

    @property
    def end_stage(self) -> PipelineStage:
        """Return the last stage to process."""

    @property
    def language(self) -> str:
        """Return the run language."""

    @property
    def tts_audio_output(self) -> str | dict[str, Any] | None:
        """Return the requested TTS output options."""

    @property
    def wake_word_settings(self) -> WakeWordSettings | None:
        """Return wake word settings."""

    @property
    def audio_settings(self) -> AudioSettings:
        """Return audio processing settings."""

    @property
    def device_id(self) -> str | None:
        """Return the device associated with the run."""

    @property
    def satellite_id(self) -> str | None:
        """Return the satellite associated with the run."""

    @callback
    def process_event(self, event: PipelineEvent) -> None:
        """Forward a pipeline event."""

    @callback
    def capture_audio(self, audio_bytes: bytes | None) -> None:
        """Capture an audio chunk."""

    @callback
    def start_debug_recording(self, name: str) -> None:
        """Start a new debug recording."""

    @callback
    def accept_wake_word(self, wake_word_phrase: str) -> None:
        """Apply the duplicate wake-up policy."""


@dataclass
class _DefaultPipelineProcessor:
    """Process the stages in a default Assist pipeline."""

    host: _PipelineController
    stt_provider: stt.SpeechToTextEntity | stt.Provider = field(init=False, repr=False)
    tts_stream: tts.ResultStream | None = field(init=False, default=None)
    wake_word_entity_id: str | None = field(init=False, default=None, repr=False)
    wake_word_entity: wake_word.WakeWordDetectionEntity = field(init=False, repr=False)
    audio_enhancer: AudioEnhancer | None = field(init=False, default=None)
    audio_chunking_buffer: AudioBuffer = field(
        init=False, default_factory=lambda: AudioBuffer(BYTES_PER_CHUNK)
    )
    _conversation_data: PipelineConversationData | None = field(
        init=False, default=None
    )
    _intent_agent_only: bool = field(init=False, default=False)
    _streamed_response: bool = field(init=False, default=False)
    """True if the response streams into the TTS stream while the agent runs."""
    _agent_audio_input: bool = field(init=False, default=False)
    """True if the conversation agent receives the spoken audio instead of STT."""
    _agent_audio_output: bool = field(init=False, default=False)
    """True if the conversation agent provides the response audio instead of TTS."""
    _pending_intent_start: dict[str, Any] | None = field(init=False, default=None)
    """Data of the start of intent recognition, held back while the agent listens."""
    _held_response_audio: tuple[tts.PcmFormat, AsyncGenerator[bytes]] | None = field(
        init=False, default=None
    )
    """Response audio the agent set while it was still listening."""
    _agent_listening_ended: asyncio.Event = field(
        init=False, default_factory=asyncio.Event
    )
    _stopped_early: asyncio.Event = field(init=False, default_factory=asyncio.Event)
    """Set when the run stops early, which also ends the audio of the agent."""
    _invalidated: bool = field(init=False, default=False)
    _stt_last_timestamp_ms: int | None = field(init=False, default=None)
    _audio_run: voice_support.AudioRun | None = field(
        init=False, default=None, repr=False
    )
    _sent_stt_vad_end: bool = field(init=False, default=False)
    intent_agent: conversation.AgentInfo | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        """Initialize audio processing."""
        if self.host.audio_settings.needs_processor:
            self.audio_enhancer = MicroVadSpeexEnhancer(
                self.host.audio_settings.auto_gain_dbfs,
                self.host.audio_settings.noise_suppression_level,
                self.host.audio_settings.is_vad_enabled,
            )

    @property
    def response_audio(self) -> tts.ResultStream | None:
        """Return the response audio stream."""
        return self.tts_stream

    @property
    def supports_streaming_response(self) -> bool | None:
        """Return whether response audio can be streamed."""
        if self.tts_stream is None:
            return None
        if self._agent_audio_output:
            return True
        if not self.tts_stream.supports_streaming_input:
            return False
        if self.intent_agent is None:
            return None
        return self.intent_agent.supports_streaming

    @callback
    def invalidate(self) -> None:
        """Invalidate this processor's active input."""
        self._invalidated = True

    @callback
    def cleanup(self) -> None:
        """Clean up resources when a run stops early."""
        self._stopped_early.set()
        if self.tts_stream is not None:
            self.tts_stream.delete()
            self.tts_stream = None

    async def prepare_wake_word_detection(self) -> None:
        """Prepare wake-word-detection."""
        entity_id = (
            self.host.pipeline.wake_word_entity
            or wake_word.async_default_entity(self.host.hass)
        )
        if entity_id is None:
            raise WakeWordDetectionError(
                code="wake-engine-missing",
                message="No wake word engine",
            )

        wake_word_entity = wake_word.async_get_wake_word_detection_entity(
            self.host.hass, entity_id
        )
        if wake_word_entity is None:
            raise WakeWordDetectionError(
                code="wake-provider-missing",
                message=f"No wake-word-detection provider for: {entity_id}",
            )

        self.wake_word_entity_id = entity_id
        self.wake_word_entity = wake_word_entity

    async def wake_word_detection(
        self,
        stream: AsyncIterable[EnhancedAudioChunk],
        audio_chunks_for_stt: list[EnhancedAudioChunk],
    ) -> wake_word.DetectionResult | None:
        """Run wake-word-detection portion of pipeline. Returns detection result."""
        metadata_dict = asdict(
            stt.SpeechMetadata(
                language="",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            )
        )

        wake_word_settings = self.host.wake_word_settings or WakeWordSettings()

        # Remove language since it doesn't apply to wake words yet
        metadata_dict.pop("language", None)

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_START,
                {
                    "entity_id": self.wake_word_entity_id,
                    "metadata": metadata_dict,
                    "timeout": wake_word_settings.timeout or 0,
                },
            )
        )

        self.host.start_debug_recording(f"00_wake-{self.wake_word_entity_id}")

        wake_word_vad: VoiceActivityTimeout | None = None
        if (wake_word_settings.timeout is not None) and (
            wake_word_settings.timeout > 0
        ):
            # Use VAD to determine timeout
            wake_word_vad = VoiceActivityTimeout(wake_word_settings.timeout)

        # Audio chunk buffer. This audio will be forwarded to speech-to-text
        # after wake-word-detection.
        num_audio_chunks_to_buffer = int(
            (wake_word_settings.audio_seconds_to_buffer * SAMPLE_RATE)
            / SAMPLES_PER_CHUNK
        )

        stt_audio_buffer: deque[EnhancedAudioChunk] | None = None
        if num_audio_chunks_to_buffer > 0:
            stt_audio_buffer = deque(maxlen=num_audio_chunks_to_buffer)

        try:
            # Detect wake word(s)
            result = await self.wake_word_entity.async_process_audio_stream(
                self._wake_word_audio_stream(
                    audio_stream=stream,
                    stt_audio_buffer=stt_audio_buffer,
                    wake_word_vad=wake_word_vad,
                ),
                self.host.pipeline.wake_word_id,
            )

            if stt_audio_buffer is not None:
                # All audio kept from right before the wake word was detected as
                # a single chunk.
                audio_chunks_for_stt.extend(stt_audio_buffer)
        except WakeWordDetectionAborted:
            raise
        except WakeWordTimeoutError:
            _LOGGER.debug("Timeout during wake word detection")
            raise
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during wake-word-detection")
            raise WakeWordDetectionError(
                code="wake-stream-failed",
                message="Unexpected error during wake-word-detection",
            ) from src_error

        _LOGGER.debug("wake-word-detection result %s", result)

        if result is None:
            wake_word_output: dict[str, Any] = {}
        else:
            self.host.accept_wake_word(result.wake_word_phrase)

            if result.queued_audio:
                # Add audio that was pending at detection.
                #
                # Because detection occurs *after* the wake word was actually
                # spoken, we need to make sure pending audio is forwarded to
                # speech-to-text so the user does not have to pause before
                # speaking the voice command.
                audio_chunks_for_stt.extend(
                    EnhancedAudioChunk(
                        audio=chunk_ts[0],
                        timestamp_ms=chunk_ts[1],
                        speech_probability=None,
                    )
                    for chunk_ts in result.queued_audio
                )

            wake_word_output = asdict(result)

            # Remove non-JSON fields
            wake_word_output.pop("queued_audio", None)

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_END,
                {"wake_word_output": wake_word_output},
            )
        )

        return result

    async def _wake_word_audio_stream(
        self,
        audio_stream: AsyncIterable[EnhancedAudioChunk],
        stt_audio_buffer: deque[EnhancedAudioChunk] | None,
        wake_word_vad: VoiceActivityTimeout | None,
        sample_rate: int = SAMPLE_RATE,
        sample_width: int = SAMPLE_WIDTH,
    ) -> AsyncIterable[tuple[bytes, int]]:
        """Yield audio chunks with timestamps (milliseconds since start of stream).

        Adds audio to a ring buffer that will be forwarded to speech-to-text after
        detection. Times out if VAD detects enough silence.
        """
        async for chunk in audio_stream:
            if self._invalidated:
                raise WakeWordDetectionAborted

            self.host.capture_audio(chunk.audio)
            yield chunk.audio, chunk.timestamp_ms

            # Wake-word-detection occurs *after* the wake word was actually
            # spoken. Keeping audio right before detection allows the voice
            # command to be spoken immediately after the wake word.
            if stt_audio_buffer is not None:
                stt_audio_buffer.append(chunk)

            if wake_word_vad is not None:
                chunk_seconds = (len(chunk.audio) // sample_width) / sample_rate
                if not wake_word_vad.process(chunk_seconds, chunk.speech_probability):
                    raise WakeWordTimeoutError(
                        code="wake-word-timeout", message="Wake word was not detected"
                    )

    async def prepare_speech_to_text(
        self, metadata: stt.SpeechMetadata, engine: str, language: str
    ) -> None:
        """Prepare speech-to-text."""
        stt_provider = stt.async_get_speech_to_text_engine(self.host.hass, engine)

        if stt_provider is None:
            raise SpeechToTextError(
                code="stt-provider-missing",
                message=f"No speech-to-text provider for: {engine}",
            )

        metadata.language = language

        if not stt_provider.check_metadata(metadata):
            raise SpeechToTextError(
                code="stt-provider-unsupported-metadata",
                message=(
                    f"Provider {stt_provider.name} does not support input speech "
                    f"to text metadata {metadata}"
                ),
            )

        self.stt_provider = stt_provider

    async def speech_to_text(
        self,
        metadata: stt.SpeechMetadata,
        stream: AsyncIterable[EnhancedAudioChunk],
    ) -> str:
        """Run speech-to-text portion of pipeline. Returns the spoken text."""
        # Create a background task to prepare the conversation agents
        if self.intent_agent:
            self.host.hass.async_create_background_task(
                self._async_prepare_intent_agents(self.intent_agent.id),
                f"prepare conversation agent {self.intent_agent.id}",
            )

        if isinstance(self.stt_provider, stt.Provider):
            engine = self.stt_provider.name
        else:
            engine = self.stt_provider.entity_id

        audio_processing = self.stt_provider.async_get_audio_processing(metadata)
        is_vad_enabled = self.host.audio_settings.is_vad_enabled
        provider_vad = is_vad_enabled and not audio_processing.requires_external_vad

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": engine,
                    "metadata": asdict(metadata),
                    "audio_processing": asdict(audio_processing),
                },
            )
        )

        self.host.start_debug_recording(f"01_stt-{engine}")

        # While the run listens, it alone says where the command ends,
        # and what it said stands once it is done
        run: voice_support.AudioRun | None = None
        if (
            is_vad_enabled
            and (self._audio_run is not None)
            and (
                self._audio_run.listening
                or (self._audio_run.speech_ended_ms is not None)
            )
        ):
            run = self._audio_run

        stt_vad: VoiceCommandSegmenter | None = None
        command_timeout_ms: int | None = None
        if is_vad_enabled and audio_processing.requires_external_vad:
            if run is None:
                stt_vad = VoiceCommandSegmenter(
                    silence_seconds=self.host.audio_settings.silence_seconds
                )
            else:
                command_timeout_ms = RUN_COMMAND_TIMEOUT_MS

        try:
            # Transcribe audio stream
            process_audio_stream = (
                self.stt_provider.async_process_audio_stream
                if isinstance(self.stt_provider, stt.Provider)
                else self.stt_provider.internal_async_process_audio_stream
            )
            result = await process_audio_stream(
                metadata,
                self._speech_to_text_stream(
                    audio_stream=stream,
                    stt_vad=stt_vad,
                    run=run,
                    command_timeout_ms=command_timeout_ms,
                ),
            )
        except asyncio.CancelledError, TimeoutError:
            raise  # expected
        except hass_nabucasa.auth.Unauthenticated as src_error:
            raise SpeechToTextError(
                code="cloud-auth-failed",
                message="Home Assistant Cloud authentication failed",
            ) from src_error
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during speech-to-text")
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="Unexpected error during speech-to-text",
            ) from src_error

        _LOGGER.debug("speech-to-text result %s", result)

        # The provider found the end of speech by returning the transcript --
        # unless something already said where the command ended, or the run
        # did so at or past the end of the audio.
        if not self._sent_stt_vad_end:
            if (run is not None) and (run.speech_ended_ms is not None):
                self._async_stt_vad_end(run.speech_ended_ms)
            elif provider_vad:
                self._async_stt_vad_end(self._stt_last_timestamp_ms or 0)

        if result.result != stt.SpeechResultState.SUCCESS:
            raise SpeechToTextError(
                code="stt-stream-failed",
                message="speech-to-text failed",
            )

        if not result.text:
            raise SpeechToTextError(
                code="stt-no-text-recognized", message="No text recognized"
            )

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.STT_END,
                {
                    "stt_output": {
                        "text": result.text,
                    }
                },
            )
        )

        return result.text

    async def _speech_to_text_stream(
        self,
        audio_stream: AsyncIterable[EnhancedAudioChunk],
        stt_vad: VoiceCommandSegmenter | None,
        run: voice_support.AudioRun | None = None,
        command_timeout_ms: int | None = None,
        sample_rate: int = SAMPLE_RATE,
        sample_width: int = SAMPLE_WIDTH,
    ) -> AsyncGenerator[bytes]:
        """Yield audio chunks until the command ends or speech-to-text completes.

        While the run listens it alone says where the command ends; a run
        that goes away mid-command ends it there.
        """
        sent_vad_start = False
        first_timestamp_ms: int | None = None

        async for chunk in audio_stream:
            self.host.capture_audio(chunk.audio)

            if run is not None:
                if first_timestamp_ms is None:
                    first_timestamp_ms = chunk.timestamp_ms

                if (not sent_vad_start) and (run.speech_started_ms is not None):
                    self._async_stt_vad_start(run.speech_started_ms)
                    sent_vad_start = True

                # The run hears the audio ahead of speech-to-text
                if (run.speech_ended_ms is not None) and (
                    chunk.timestamp_ms >= run.speech_ended_ms
                ):
                    self._async_stt_vad_end(run.speech_ended_ms)
                    break

                if (not run.listening) and (run.speech_ended_ms is None):
                    _LOGGER.debug(
                        "The run stopped listening at %s ms",
                        chunk.timestamp_ms,
                    )
                    self._async_stt_vad_end(chunk.timestamp_ms)
                    break

                if (command_timeout_ms is not None) and (
                    chunk.timestamp_ms - first_timestamp_ms >= command_timeout_ms
                ):
                    _LOGGER.debug(
                        "The run did not end the command within %s ms",
                        command_timeout_ms,
                    )
                    self._async_stt_vad_end(chunk.timestamp_ms)
                    break

            if stt_vad is not None:
                chunk_seconds = (len(chunk.audio) // sample_width) / sample_rate
                if not stt_vad.process(chunk_seconds, chunk.speech_probability):
                    # Silence detected at the end of voice command
                    self._async_stt_vad_end(chunk.timestamp_ms)
                    break

                if stt_vad.in_command and (not sent_vad_start):
                    # Speech detected at start of voice command
                    self._async_stt_vad_start(chunk.timestamp_ms)
                    sent_vad_start = True

            self._stt_last_timestamp_ms = chunk.timestamp_ms
            yield chunk.audio

    @callback
    def start_agent_audio_input(
        self,
        metadata: stt.SpeechMetadata,
        stream: AsyncIterable[EnhancedAudioChunk],
    ) -> conversation.ConversationAudioInput:
        """Start sending the spoken audio to the conversation agent.

        The agent finds the end of the voice command itself, so the audio goes
        on until it adds the transcript.
        """
        assert self.intent_agent is not None

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.STT_START,
                {"engine": self.intent_agent.id, "metadata": asdict(metadata)},
            )
        )
        self.host.start_debug_recording(f"01_stt-{self.intent_agent.id}")

        async def agent_audio_stream() -> AsyncGenerator[bytes]:
            async for chunk in self._speech_to_text_stream(
                # Satellites stop sending audio when listening ends, so a read
                # that waits for more must end with it
                audio_stream=_async_until(stream, self._agent_listening_ended),
                stt_vad=None,
            ):
                yield chunk

        return conversation.ConversationAudioInput(
            pcm_format=tts.PcmFormat(
                sample_rate=SAMPLE_RATE,
                sample_width=SAMPLE_WIDTH,
                channels=SAMPLE_CHANNELS,
            ),
            stream=agent_audio_stream(),
        )

    @callback
    def _async_end_agent_listening(self, transcript: str = "") -> None:
        """End speech-to-text of the agent and start intent recognition, once.

        Listening ends when the agent adds the transcript, or returns without one.
        """
        if (intent_start := self._pending_intent_start) is None:
            return

        self._pending_intent_start = None
        self._agent_listening_ended.set()
        # Even if the agent never reads its audio again
        self.host.hass.async_create_task(
            self._async_close_audio_run(), "close the audio run of the agent"
        )
        # The agent found the end of speech; satellites stop listening there
        self._async_stt_vad_end(self._stt_last_timestamp_ms or 0)
        self.host.process_event(
            PipelineEvent(
                PipelineEventType.STT_END, {"stt_output": {"text": transcript}}
            )
        )
        self.host.process_event(
            PipelineEvent(PipelineEventType.INTENT_START, intent_start)
        )
        if (held_audio := self._held_response_audio) is not None:
            self._held_response_audio = None
            self._async_play_response_audio(*held_audio)

    @callback
    def async_set_audio_stream(
        self, pcm_format: tts.PcmFormat, audio_stream: AsyncGenerator[bytes]
    ) -> None:
        """Play the spoken response of the conversation agent.

        With audio input, it plays once the agent has added the transcript.
        """
        if self._streamed_response or (self._held_response_audio is not None):
            raise RuntimeError("The response audio of this turn is already set")

        if self._pending_intent_start is not None:
            self._held_response_audio = (pcm_format, audio_stream)
            return

        self._async_play_response_audio(pcm_format, audio_stream)

    @callback
    def _async_play_response_audio(
        self, pcm_format: tts.PcmFormat, audio_stream: AsyncGenerator[bytes]
    ) -> None:
        """Start playing the spoken response of the conversation agent."""
        assert self.tts_stream is not None
        self._streamed_response = True
        # Its audio would otherwise outlive a cancelled run
        self.tts_stream.async_set_audio_stream(
            pcm_format, _async_until(audio_stream, self._stopped_early)
        )
        self.host.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_PROGRESS,
                {"tts_start_streaming": True},
            )
        )

    @callback
    def _async_stt_vad_start(self, timestamp_ms: int) -> None:
        """Send STT_VAD_START."""
        self.host.process_event(
            PipelineEvent(PipelineEventType.STT_VAD_START, {"timestamp": timestamp_ms})
        )

    @callback
    def _async_stt_vad_end(self, timestamp_ms: int) -> None:
        """Send STT_VAD_END and record that it was sent."""
        self._sent_stt_vad_end = True
        self.host.process_event(
            PipelineEvent(PipelineEventType.STT_VAD_END, {"timestamp": timestamp_ms})
        )

    @callback
    def _accept_wake_word_audio(
        self,
        wake_word_phrase: str,
        wake_word_audio_ms: int,
        verdict: voice_support.WakeWordAccepted | voice_support.WakeWordRejected | None,
    ) -> bool:
        """Accept the wake word whose audio starts the stream, unless refused.

        Accepting starts the duplicate cooldown, which a refused detection
        must not do, so the run's verdict comes first.
        """
        wake_word_output: dict[str, Any] = {
            "wake_word_phrase": wake_word_phrase,
            "wake_word_audio_ms": wake_word_audio_ms,
        }
        if isinstance(verdict, voice_support.WakeWordRejected):
            accepted = False
            wake_word_output["reason"] = verdict.reason or "unverified"
        else:
            self.host.accept_wake_word(wake_word_phrase)
            accepted = True

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.WAKE_WORD_END
                if accepted
                else PipelineEventType.WAKE_WORD_REJECTED,
                {"wake_word_output": wake_word_output},
            )
        )
        return accepted

    async def prepare_recognize_intent(self, session: chat_session.ChatSession) -> None:
        """Prepare recognizing an intent."""
        self._conversation_data = async_get_pipeline_conversation_data(
            self.host.hass, session
        )

        if (
            continue_agent := self._conversation_data.continue_conversation_agent
        ) is not None:
            agent_info = conversation.async_get_agent_info(
                self.host.hass, continue_agent
            )
            if agent_info is None:
                self._conversation_data.continue_conversation_agent = None
                raise IntentRecognitionError(
                    code="intent-agent-not-found",
                    message=(
                        f"Intent recognition engine {continue_agent}"
                        " asked for follow-up but is no longer found"
                    ),
                )
            # The run takes the follow-up once it is valid
            self._intent_agent_only = True

        else:
            agent_info = conversation.async_get_agent_info(
                self.host.hass,
                self.host.pipeline.conversation_engine
                or conversation.HOME_ASSISTANT_AGENT,
            )

            if agent_info is None:
                engine = self.host.pipeline.conversation_engine or "default"
                raise IntentRecognitionError(
                    code="intent-not-supported",
                    message=f"Intent recognition engine {engine} is not found",
                )

        self.intent_agent = agent_info

    def _intent_input_language(self) -> str:
        """Return the language that intent recognition uses."""
        if self.host.pipeline.conversation_language == MATCH_ALL:
            # LLMs support all languages ('*') so use languages from the
            # pipeline for intent fallback.
            #
            # We prioritize the STT and TTS languages because they may be more
            # specific, such as "zh-CN" instead of just "zh". This is necessary
            # for languages whose intents are split out by region when
            # preferring local intent matching.
            return (
                self.host.pipeline.stt_language
                or self.host.pipeline.tts_language
                or self.host.pipeline.language
            )
        return self.host.pipeline.conversation_language

    async def _async_prepare_intent_agents(self, agent_id: str) -> None:
        """Prepare the agents that intent recognition uses."""
        language = self._intent_input_language()
        # Local intents run on the default agent before the pipeline agent.
        # Without them, loading the language intents would only cost memory.
        if (
            agent_id != conversation.HOME_ASSISTANT_AGENT
            and self.host.pipeline.prefer_local_intents
            and not self._intent_agent_only
            and not self._agent_audio_output
        ):
            await conversation.async_prepare_intents(self.host.hass, language)
        await conversation.async_prepare_agent(self.host.hass, agent_id, language)

    async def recognize_intent(  # noqa: C901
        self,
        intent_input: str | None,
        conversation_id: str,
        conversation_extra_system_prompt: str | None,
        audio: conversation.ConversationAudioInput | None = None,
    ) -> tuple[str, bool]:
        """Run intent recognition portion of pipeline.

        The conversation agent gets either the text or the spoken audio.

        Returns (speech, all_targets_in_satellite_area).
        """
        if self.intent_agent is None or self._conversation_data is None:
            raise RuntimeError("Recognize intent was not prepared")

        input_language = self._intent_input_language()

        intent_start = {
            "engine": self.intent_agent.id,
            "language": input_language,
            "intent_input": intent_input,
            "conversation_id": conversation_id,
            "device_id": self.host.device_id,
            "satellite_id": self.host.satellite_id,
            "prefer_local_intents": self.host.pipeline.prefer_local_intents,
        }
        if audio is None:
            self.host.process_event(
                PipelineEvent(PipelineEventType.INTENT_START, intent_start)
            )
        else:
            # Satellites keep listening until the agent has heard the user
            self._pending_intent_start = intent_start

        try:
            # The audio of the agent replaces any speech of its text
            if (
                self.tts_stream
                and self.tts_stream.supports_streaming_input
                and not self._agent_audio_output
            ):
                tts_input_stream: asyncio.Queue[str | None] | None = asyncio.Queue()
            else:
                tts_input_stream = None
            chat_log_role = None
            delta_character_count = 0
            last_assistant_content = ""

            @callback
            def chat_log_delta_listener(
                chat_log: conversation.ChatLog, delta: dict
            ) -> None:
                """Handle chat log delta."""
                if delta.get("role") == "user":
                    # Listeners get the transcript of spoken audio in stt-end
                    if self._pending_intent_start is not None:
                        self._async_end_agent_listening(delta["content"])
                    return

                self.host.process_event(
                    PipelineEvent(
                        PipelineEventType.INTENT_PROGRESS,
                        {
                            "chat_log_delta": delta,
                        },
                    )
                )
                if tts_input_stream is None:
                    return

                nonlocal chat_log_role, last_assistant_content

                if role := delta.get("role"):
                    chat_log_role = role

                    # Keep TTS from running a new assistant message into the
                    # previous one, for example around a tool call
                    if (
                        role == "assistant"
                        and last_assistant_content
                        and not last_assistant_content[-1].isspace()
                    ):
                        tts_input_stream.put_nowait(" ")
                        last_assistant_content = " "

                # We are only interested in assistant deltas
                if chat_log_role != "assistant":
                    return

                if content := delta.get("content"):
                    tts_input_stream.put_nowait(content)
                    last_assistant_content = content

                if self._streamed_response:
                    return

                nonlocal delta_character_count

                # Streamed responses are not cached. That's why we
                # only start streaming text after we have received
                # enough characters that indicates it will be a long
                # response or if we have received text, and then a
                # tool call.

                # Tool call after we already received text
                start_streaming = delta_character_count > 0 and delta.get("tool_calls")

                # Count characters in the content and test if we
                # exceed streaming threshold
                if not start_streaming and content:
                    delta_character_count += len(content)
                    start_streaming = delta_character_count > STREAM_RESPONSE_CHARS

                if not start_streaming:
                    return

                self._streamed_response = True

                self.host.process_event(
                    PipelineEvent(
                        PipelineEventType.INTENT_PROGRESS,
                        {
                            "tts_start_streaming": True,
                        },
                    )
                )

                async def tts_input_stream_generator() -> AsyncGenerator[str]:
                    """Yield TTS input stream."""
                    while (tts_input := await tts_input_stream.get()) is not None:
                        yield tts_input

                # Concatenate all existing queue items
                parts = []
                while not tts_input_stream.empty():
                    parts.append(tts_input_stream.get_nowait())
                tts_input_stream.put_nowait(
                    "".join(
                        # At this point parts is only strings,
                        # None indicates end of queue
                        cast(list[str], parts)
                    )
                )

                assert self.tts_stream is not None
                self.tts_stream.async_set_message_stream(tts_input_stream_generator())

            user_input = conversation.ConversationInput(
                text=intent_input or "",
                context=self.host.context,
                conversation_id=conversation_id,
                device_id=self.host.device_id,
                satellite_id=self.host.satellite_id,
                language=input_language,
                agent_id=self.intent_agent.id,
                extra_system_prompt=conversation_extra_system_prompt,
                audio=audio,
                audio_output=self if self._agent_audio_output else None,
            )

            with (
                chat_session.async_get_chat_session(
                    self.host.hass,
                    user_input.conversation_id,
                    context=user_input.context,
                ) as session,
                conversation.async_get_chat_log(
                    self.host.hass,
                    session,
                    user_input,
                    chat_log_delta_listener=chat_log_delta_listener,
                ) as chat_log,
            ):
                agent_id = self.intent_agent.id
                processed_locally = agent_id == conversation.HOME_ASSISTANT_AGENT
                all_targets_in_satellite_area = False
                intent_response: intent.IntentResponse | None = None
                # The agent hears spoken audio before there is text to match, and
                # a local response would not have the voice of an agent that speaks
                if (
                    not processed_locally
                    and not self._intent_agent_only
                    and audio is None
                    and not self._agent_audio_output
                ):
                    # Sentence triggers override conversation agent
                    if (
                        trigger_response_text
                        := await conversation.async_handle_sentence_triggers(
                            self.host.hass, user_input, chat_log
                        )
                    ) is not None:
                        # Sentence trigger matched
                        agent_id = "sentence_trigger"
                        processed_locally = True
                        intent_response = intent.IntentResponse(
                            self.host.pipeline.conversation_language
                        )
                        intent_response.async_set_speech(trigger_response_text)

                    intent_filter: Callable[[RecognizeResult], bool] | None = None
                    # If the LLM has API access, we filter out some sentences that are
                    # interfering with LLM operation.
                    if (
                        intent_agent_state := self.host.hass.states.get(
                            self.intent_agent.id
                        )
                    ) and intent_agent_state.attributes.get(
                        EntityStateAttribute.SUPPORTED_FEATURES, 0
                    ) & conversation.ConversationEntityFeature.CONTROL:
                        intent_filter = _async_local_fallback_intent_filter

                    # Try local intents
                    if (
                        intent_response is None
                        and self.host.pipeline.prefer_local_intents
                        and (
                            intent_response := await conversation.async_handle_intents(
                                self.host.hass,
                                user_input,
                                chat_log,
                                intent_filter=intent_filter,
                            )
                        )
                    ):
                        # Local intent matched
                        agent_id = conversation.HOME_ASSISTANT_AGENT
                        processed_locally = True

                # It was already handled, create response and add to chat history
                if intent_response is not None:
                    speech: str = intent_response.speech.get("plain", {}).get(
                        "speech", ""
                    )
                    chat_log.async_add_assistant_content_without_tools(
                        conversation.AssistantContent(
                            agent_id=agent_id,
                            content=speech,
                        )
                    )
                    conversation_result = conversation.ConversationResult(
                        response=intent_response,
                        conversation_id=session.conversation_id,
                    )

                else:
                    # Fall back to pipeline conversation agent
                    conversation_result = await conversation.async_converse(
                        hass=self.host.hass,
                        text=user_input.text,
                        conversation_id=user_input.conversation_id,
                        device_id=user_input.device_id,
                        satellite_id=user_input.satellite_id,
                        context=user_input.context,
                        language=user_input.language,
                        agent_id=user_input.agent_id,
                        extra_system_prompt=user_input.extra_system_prompt,
                        audio=user_input.audio,
                        audio_output=user_input.audio_output,
                    )
                    speech = conversation_result.response.speech.get("plain", {}).get(
                        "speech", ""
                    )
                    # Agents that do not use the chat log only answer in their result.
                    if chat_log.content[-1].role == "user" and speech:
                        chat_log.async_add_assistant_content_without_tools(
                            conversation.AssistantContent(
                                agent_id=agent_id,
                                content=speech,
                            )
                        )
                    if tts_input_stream and self._streamed_response:
                        tts_input_stream.put_nowait(None)

                if agent_id == conversation.HOME_ASSISTANT_AGENT:
                    # Check if all targeted entities were in the same area as
                    # the satellite device.
                    # If so, the satellite should respond with an acknowledge beep
                    # instead of a full response.
                    all_targets_in_satellite_area = (
                        self._get_all_targets_in_satellite_area(
                            conversation_result.response,
                            self.host.satellite_id,
                            self.host.device_id,
                        )
                    )

        except conversation.ConversationBusyError as src_error:
            raise IntentRecognitionError(
                code="intent-busy",
                message=str(src_error),
            ) from src_error
        except Unauthorized as src_error:
            raise IntentRecognitionError(
                code="intent-unauthorized",
                message="Not allowed to continue this conversation",
            ) from src_error
        except Exception as src_error:
            _LOGGER.exception("Unexpected error during intent recognition")
            raise IntentRecognitionError(
                code="intent-failed",
                message="Unexpected error during intent recognition",
            ) from src_error
        finally:
            # For an agent that returns without a transcript
            self._async_end_agent_listening()

        _LOGGER.debug("conversation result %s", conversation_result)

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_END,
                {
                    "processed_locally": processed_locally,
                    "intent_output": conversation_result.as_dict(),
                },
            )
        )

        if conversation_result.continue_conversation:
            self._conversation_data.continue_conversation_agent = agent_id

        return (speech, all_targets_in_satellite_area)

    def _get_all_targets_in_satellite_area(
        self,
        intent_response: intent.IntentResponse,
        satellite_id: str | None,
        device_id: str | None,
    ) -> bool:
        """Return true if all targeted entities were in the same area as the device."""
        if (
            intent_response.response_type is not intent.IntentResponseType.ACTION_DONE
            or not intent_response.matched_states
        ):
            return False

        entity_registry = er.async_get(self.host.hass)
        device_registry = dr.async_get(self.host.hass)

        area_id: str | None = None

        if (
            satellite_id is not None
            and (target_entity_entry := entity_registry.async_get(satellite_id))
            is not None
        ):
            area_id = target_entity_entry.area_id
            device_id = target_entity_entry.device_id

        if area_id is None:
            if device_id is None:
                return False

            device_entry = device_registry.async_get(device_id)
            if device_entry is None:
                return False

            area_id = dr.async_get_effective_area_id(self.host.hass, device_entry)
            if area_id is None:
                return False

        for state in intent_response.matched_states:
            target_entity_entry = entity_registry.async_get(state.entity_id)
            if target_entity_entry is None:
                return False

            target_area_id = target_entity_entry.area_id
            if target_area_id is None:
                if target_entity_entry.device_id is None:
                    return False

                target_device_entry = device_registry.async_get(
                    target_entity_entry.device_id
                )
                if target_device_entry is None:
                    return False

                target_area_id = dr.async_get_effective_area_id(
                    self.host.hass, target_device_entry
                )

            if target_area_id != area_id:
                return False

        return True

    def _has_spoken_response(
        self, tts_input: str, all_targets_in_satellite_area: bool
    ) -> bool:
        """Return True if the response of intent recognition can be spoken."""
        if self._streamed_response:
            return True
        if (self.tts_stream is not None) and (self.tts_stream.engine is None):
            # Without an engine, only the agent could speak the response
            return False
        return all_targets_in_satellite_area or bool(tts_input.strip())

    async def prepare_text_to_speech(self) -> None:
        """Prepare text-to-speech."""
        engine = self.host.pipeline.tts_engine
        language = self.host.pipeline.tts_language
        voice = self.host.pipeline.tts_voice
        if self._agent_audio_output:
            # Replies without audio from the agent use the default engine, if any
            engine, language, voice = async_resolve_tts_engine_language_voice(
                self.host.hass, self.host.language
            ) or (None, None, None)

        tts_options: dict[str, Any] = {}
        if voice is not None:
            tts_options[TextToSpeechCommonOption.VOICE] = voice

        if isinstance(self.host.tts_audio_output, dict):
            tts_options.update(self.host.tts_audio_output)
        elif isinstance(self.host.tts_audio_output, str):
            tts_options[TextToSpeechCommonOption.PREFERRED_FORMAT] = (
                self.host.tts_audio_output
            )
            if self.host.tts_audio_output == "wav":
                # 16 Khz, 16-bit mono
                tts_options[TextToSpeechCommonOption.PREFERRED_SAMPLE_RATE] = (
                    SAMPLE_RATE
                )
                tts_options[TextToSpeechCommonOption.PREFERRED_SAMPLE_CHANNELS] = (
                    SAMPLE_CHANNELS
                )
                tts_options[TextToSpeechCommonOption.PREFERRED_SAMPLE_BYTES] = (
                    SAMPLE_WIDTH
                )

        if engine is None:
            # Only the agent can speak the response
            try:
                self.tts_stream = tts.async_create_audio_stream(
                    self.host.hass, options=tts_options
                )
            except HomeAssistantError as err:
                raise TextToSpeechError(
                    code="tts-not-supported",
                    message=(
                        f"Response audio does not support options {tts_options}: {err}"
                    ),
                ) from err
            return

        try:
            self.tts_stream = tts.async_create_stream(
                hass=self.host.hass,
                engine=engine,
                language=language,
                options=tts_options,
            )
        except HomeAssistantError as err:
            raise TextToSpeechError(
                code="tts-not-supported",
                message=(
                    f"Text-to-speech engine {engine} "
                    f"does not support language {language}"
                    f" or options {tts_options}:"
                    f" {err}"
                ),
            ) from err

    async def text_to_speech(
        self, tts_input: str, override_media_path: Path | None = None
    ) -> None:
        """Run text-to-speech portion of pipeline."""
        assert self.tts_stream is not None

        engine = self.tts_stream.engine
        if self._agent_audio_output and self._streamed_response and self.intent_agent:
            # Like for speech-to-text, the agent is the engine of its own audio
            engine = self.intent_agent.id

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": engine,
                    "language": self.host.pipeline.tts_language,
                    "voice": self.host.pipeline.tts_voice,
                    "tts_input": tts_input,
                    "acknowledge_override": override_media_path is not None,
                },
            )
        )

        if override_media_path:
            self.tts_stream.async_override_result(override_media_path)
        elif not self._streamed_response:
            self.tts_stream.async_set_message(tts_input)

        tts_output = {
            "media_id": self.tts_stream.media_source_id,
            "token": self.tts_stream.token,
            "url": self.tts_stream.url,
            "mime_type": self.tts_stream.content_type,
        }

        self.host.process_event(
            PipelineEvent(PipelineEventType.TTS_END, {"tts_output": tts_output})
        )

    async def process_volume_only(
        self, audio_stream: AsyncIterable[bytes], start_ms: int = 0
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Apply volume transformation only with optional chunking.

        No VAD/audio enhancements are applied.
        """
        timestamp_ms = start_ms
        async for chunk in audio_stream:
            if self.host.audio_settings.volume_multiplier != 1.0:
                chunk = audioop.mul(
                    chunk, SAMPLE_WIDTH, self.host.audio_settings.volume_multiplier
                )

            for sub_chunk in chunk_samples(
                chunk, BYTES_PER_CHUNK, self.audio_chunking_buffer
            ):
                yield EnhancedAudioChunk(
                    audio=sub_chunk,
                    timestamp_ms=timestamp_ms,
                    speech_probability=None,  # no VAD
                )
                timestamp_ms += MS_PER_CHUNK

    async def process_enhance_audio(
        self, audio_stream: AsyncIterable[bytes], start_ms: int = 0
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Split audio into chunks and apply audio enhancements.

        Applies VAD/noise suppression/auto gain/volume
        transformation.
        """
        assert self.audio_enhancer is not None

        timestamp_ms = start_ms
        async for dirty_samples in audio_stream:
            if self.host.audio_settings.volume_multiplier != 1.0:
                # Static gain
                dirty_samples = audioop.mul(
                    dirty_samples,
                    SAMPLE_WIDTH,
                    self.host.audio_settings.volume_multiplier,
                )

            # Split into chunks for audio enhancements/VAD
            for dirty_chunk in chunk_samples(
                dirty_samples, BYTES_PER_CHUNK, self.audio_chunking_buffer
            ):
                yield self.audio_enhancer.enhance_chunk(dirty_chunk, timestamp_ms)
                timestamp_ms += MS_PER_CHUNK

    async def _async_start_audio_run(
        self, request: _PipelineProcessorRequest, audio_stream: AsyncIterable[bytes]
    ) -> voice_support.AudioRun | None:
        """Open an audio run over the stream, or None to go on without one."""
        audio_settings = self.host.audio_settings
        return await voice_support.async_start_run(
            self.host.hass,
            voice_support.AudioRunRequest(
                satellite_id=self.host.satellite_id,
                wake_word_phrase=request.wake_word_phrase,
                wake_word_audio_ms=request.wake_word_audio_ms,
                # An agent that hears the user finds the end of the command
                silence_seconds=(
                    audio_settings.silence_seconds
                    if audio_settings.is_vad_enabled and not self._agent_audio_input
                    else None
                ),
            ),
            audio_stream,
        )

    async def _async_close_audio_run(self) -> None:
        """Let the run go, once the command is over or the pipeline is."""
        if self._audio_run is None:
            return
        run, self._audio_run = self._audio_run, None
        await run.async_close()

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Run the configured default pipeline stages."""
        try:
            await self._async_execute(request)
        finally:
            await self._async_close_audio_run()

    async def _async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Run the stages."""
        current_stage: PipelineStage | None = self.host.start_stage
        stt_audio_buffer: list[EnhancedAudioChunk] = []
        stt_processed_stream: AsyncIterable[EnhancedAudioChunk] | None = None
        stt_stream = request.stt_stream
        skipped_ms = 0

        wake_word_verdict: (
            voice_support.WakeWordAccepted | voice_support.WakeWordRejected | None
        ) = None
        wake_word_audio_ms = request.wake_word_audio_ms

        if (stt_stream is not None) and (current_stage == PipelineStage.STT):
            self._audio_run = await self._async_start_audio_run(request, stt_stream)

            if self._audio_run is not None:
                stt_stream = self._audio_run.async_stream()
                wake_word_verdict = await self._audio_run.async_wake_word()
                if isinstance(wake_word_verdict, voice_support.WakeWordAccepted):
                    # Something that found the wake word knows where it
                    # ends better than the threshold a device crossed.
                    wake_word_audio_ms = wake_word_verdict.wake_word_audio_ms

            if wake_word_audio_ms is not None:
                # Whole chunks only, since the partial chunk at the end is dropped
                skipped_ms = (wake_word_audio_ms // MS_PER_CHUNK) * MS_PER_CHUNK
                stt_stream = _skip_audio(
                    stt_stream, skipped_ms * BYTES_PER_CHUNK // MS_PER_CHUNK
                )

        if stt_stream is not None:
            # Timestamps count from the start of the stream, as when the
            # pipeline detects the wake word itself
            if self.host.audio_settings.needs_processor:
                # VAD/noise suppression/auto gain/volume
                stt_processed_stream = self.process_enhance_audio(
                    stt_stream, skipped_ms
                )
            else:
                # Volume multiplier only
                stt_processed_stream = self.process_volume_only(stt_stream, skipped_ms)

        if current_stage == PipelineStage.WAKE_WORD:
            # wake-word-detection
            assert stt_processed_stream is not None
            detect_result = await self.wake_word_detection(
                stt_processed_stream, stt_audio_buffer
            )
            if detect_result is None:
                # No wake word. Abort the rest of the pipeline.
                return

            current_stage = PipelineStage.STT

        # speech-to-text
        intent_input = request.intent_input
        agent_audio: conversation.ConversationAudioInput | None = None
        if current_stage == PipelineStage.STT:
            assert request.stt_metadata is not None
            assert stt_processed_stream is not None

            # Wake word detection accepts the wake word it detects
            if (self.host.start_stage == PipelineStage.STT) and (
                request.wake_word_phrase is not None
            ):
                if wake_word_audio_ms is not None:
                    if not self._accept_wake_word_audio(
                        request.wake_word_phrase,
                        wake_word_audio_ms,
                        wake_word_verdict,
                    ):
                        self.cleanup()
                        return
                else:
                    self.host.accept_wake_word(request.wake_word_phrase)

            stt_input_stream = stt_processed_stream

            if stt_audio_buffer:
                # Send audio in the buffer first to speech-to-text,
                # then move on to stt_stream.
                # This is basically an async itertools.chain.
                async def buffer_then_audio_stream() -> AsyncGenerator[
                    EnhancedAudioChunk
                ]:
                    # Buffered audio
                    for chunk in stt_audio_buffer:
                        yield chunk

                    # Streamed audio
                    assert stt_processed_stream is not None
                    async for chunk in stt_processed_stream:
                        yield chunk

                stt_input_stream = buffer_then_audio_stream()

            if self._agent_audio_input:
                agent_audio = self.start_agent_audio_input(
                    request.stt_metadata, stt_input_stream
                )
            else:
                intent_input = await self.speech_to_text(
                    request.stt_metadata,
                    stt_input_stream,
                )
                # The run ends with the command
                await self._async_close_audio_run()
            current_stage = PipelineStage.INTENT

        if self.host.end_stage != PipelineStage.STT:
            tts_input = request.tts_input
            all_targets_in_satellite_area = False

            if current_stage == PipelineStage.INTENT:
                # intent-recognition
                assert (intent_input is not None) or (agent_audio is not None)
                (
                    tts_input,
                    all_targets_in_satellite_area,
                ) = await self.recognize_intent(
                    intent_input,
                    request.session.conversation_id,
                    request.conversation_extra_system_prompt,
                    audio=agent_audio,
                )
                if self._has_spoken_response(tts_input, all_targets_in_satellite_area):
                    current_stage = PipelineStage.TTS
                else:
                    # Skip TTS
                    current_stage = PipelineStage.END

            if self.host.end_stage != PipelineStage.INTENT:
                # text-to-speech
                if current_stage == PipelineStage.TTS:
                    if all_targets_in_satellite_area:
                        # Use acknowledge media instead of full response
                        await self.text_to_speech(
                            tts_input or "", override_media_path=ACKNOWLEDGE_PATH
                        )
                    else:
                        assert tts_input is not None
                        await self.text_to_speech(tts_input)

    async def async_validate(self, request: _PipelineProcessorRequest) -> None:
        """Validate pipeline input and prepare the default stages."""
        start_stage_index = PIPELINE_STAGE_ORDER.index(self.host.start_stage)
        end_stage_index = PIPELINE_STAGE_ORDER.index(self.host.end_stage)

        # The conversation agent can replace speech-to-text and text-to-speech
        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.INTENT)
            <= end_stage_index
        ):
            await self.prepare_recognize_intent(request.session)

        stt_engine = self.host.pipeline.stt_engine
        stt_language = self.host.pipeline.stt_language or self.host.language
        if self.host.start_stage in (PipelineStage.WAKE_WORD, PipelineStage.STT):
            if stt_engine is None:
                if (
                    self.intent_agent is not None
                    and self.intent_agent.supports_audio_input
                ):
                    self._agent_audio_input = True
                # Runs for a transcript only, like the answer to a question of a
                # satellite, have no agent that can hear the user
                elif self.host.end_stage == PipelineStage.STT and (
                    default_stt := async_resolve_stt_engine_language(
                        self.host.hass, self.host.language
                    )
                ):
                    stt_engine, stt_language = default_stt
                else:
                    raise PipelineRunValidationError(
                        "the pipeline does not support speech-to-text"
                    )
            if request.stt_metadata is None:
                raise PipelineRunValidationError(
                    "stt_metadata is required for speech-to-text"
                )
            if request.stt_stream is None:
                raise PipelineRunValidationError(
                    "stt_stream is required for speech-to-text"
                )
            if (request.wake_word_audio_ms is not None) and (
                request.wake_word_phrase is None
            ):
                raise PipelineRunValidationError(
                    "wake_word_phrase is required with wake_word_audio_ms"
                )
        elif self.host.start_stage == PipelineStage.INTENT:
            if request.intent_input is None:
                raise PipelineRunValidationError(
                    "intent_input is required for intent recognition"
                )
        elif self.host.start_stage == PipelineStage.TTS:
            if request.tts_input is None:
                raise PipelineRunValidationError(
                    "tts_input is required for text-to-speech"
                )
        if self.host.end_stage == PipelineStage.TTS:
            if self.host.pipeline.tts_engine is None:
                if not (
                    self.intent_agent is not None
                    and self.intent_agent.supports_audio_output
                ):
                    raise PipelineRunValidationError(
                        "the pipeline does not support text-to-speech"
                    )
                self._agent_audio_output = True

        prepare_tasks = []

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.WAKE_WORD)
            <= end_stage_index
        ):
            prepare_tasks.append(self.prepare_wake_word_detection())

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.STT)
            <= end_stage_index
        ) and stt_engine is not None:
            assert request.stt_metadata is not None
            prepare_tasks.append(
                self.prepare_speech_to_text(
                    request.stt_metadata, stt_engine, stt_language
                )
            )

        if prepare_tasks:
            await asyncio.gather(*prepare_tasks)

        # Do TTS prepare separately so we don't create a ResultStream if the
        # pipeline is invalid.
        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.TTS)
            <= end_stage_index
        ):
            await self.prepare_text_to_speech()

        if self._intent_agent_only:
            if TYPE_CHECKING:
                assert self._conversation_data is not None
            self._conversation_data.continue_conversation_agent = None


@dataclass
class PipelineConversationData:
    """Hold data for the duration of a conversation."""

    continue_conversation_agent: str | None = None
    """The agent that requested the conversation to be continued."""


@callback
def async_get_pipeline_conversation_data(
    hass: HomeAssistant, session: chat_session.ChatSession
) -> PipelineConversationData:
    """Get the pipeline data for a specific conversation."""
    all_conversation_data = hass.data.get(KEY_PIPELINE_CONVERSATION_DATA)
    if all_conversation_data is None:
        all_conversation_data = {}
        hass.data[KEY_PIPELINE_CONVERSATION_DATA] = all_conversation_data

    data = all_conversation_data.get(session.conversation_id)
    if data is not None:
        return data

    @callback
    def do_cleanup() -> None:
        """Handle cleanup."""
        all_conversation_data.pop(session.conversation_id)

    session.async_on_cleanup(do_cleanup)
    data = all_conversation_data[session.conversation_id] = PipelineConversationData()
    return data
