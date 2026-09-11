"""Default implementation of the Assist pipeline engine."""

import array
import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import hass_nabucasa

from homeassistant.components import conversation, media_player, stt, tts, wake_word
from homeassistant.const import MATCH_ALL, EntityStateAttribute
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    chat_session,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.util.hass_dict import HassKey

from .audio_enhancer import AudioEnhancer, EnhancedAudioChunk, MicroVadSpeexEnhancer
from .audio_output import AudioOutputStream
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
    from .tool_host import PipelineToolHost

_LOGGER = logging.getLogger(__name__)

KEY_PIPELINE_CONVERSATION_DATA: HassKey[dict[str, PipelineConversationData]] = HassKey(
    "pipeline_conversation_data"
)
STREAM_RESPONSE_CHARS = 60


@callback
def _async_local_fallback_intent_filter(result: RecognizeResult) -> bool:
    """Filter out intents that are not local fallback."""
    return result.intent.name in (
        intent.INTENT_GET_STATE,
        media_player.INTENT_MEDIA_SEARCH_AND_PLAY,
    )


class _PipelineController(Protocol):
    """Home Assistant services exposed to a pipeline processor."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    start_stage: PipelineStage
    end_stage: PipelineStage
    language: str
    tts_audio_output: str | dict[str, Any] | None
    wake_word_settings: WakeWordSettings | None
    audio_settings: AudioSettings

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

    @callback
    def async_create_response_audio(
        self, extension: str, content_type: str
    ) -> AudioOutputStream:
        """Create a controller-owned response audio stream."""

    async def async_get_tool_host(self) -> PipelineToolHost:
        """Return the Home Assistant tool host for this pipeline run."""


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
    _streamed_response_text: bool = field(init=False, default=False)
    _invalidated: bool = field(init=False, default=False)
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
        if not self.tts_stream.supports_streaming_input:
            return False
        if self.intent_agent is None:
            return None
        return self.intent_agent.supports_streaming

    @property
    def start_response_immediately(self) -> bool:
        """Return whether response audio should be consumed at run start."""
        return False

    @callback
    def invalidate(self) -> None:
        """Invalidate this processor's active input."""
        self._invalidated = True

    @callback
    def cleanup(self) -> None:
        """Clean up resources after a pipeline error."""
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

    async def prepare_speech_to_text(self, metadata: stt.SpeechMetadata) -> None:
        """Prepare speech-to-text."""
        # pipeline.stt_engine can't be None or this function is not called
        stt_provider = stt.async_get_speech_to_text_engine(
            self.host.hass,
            self.host.pipeline.stt_engine,  # type: ignore[arg-type]
        )

        if stt_provider is None:
            engine = self.host.pipeline.stt_engine
            raise SpeechToTextError(
                code="stt-provider-missing",
                message=f"No speech-to-text provider for: {engine}",
            )

        metadata.language = self.host.pipeline.stt_language or self.host.language

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
        # Create a background task to prepare the conversation agent
        if self.host.end_stage >= PipelineStage.INTENT and self.intent_agent:
            self.host.hass.async_create_background_task(
                conversation.async_prepare_agent(
                    self.host.hass, self.intent_agent.id, self.host.language
                ),
                f"prepare conversation agent {self.intent_agent.id}",
            )

        if isinstance(self.stt_provider, stt.Provider):
            engine = self.stt_provider.name
        else:
            engine = self.stt_provider.entity_id

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": engine,
                    "metadata": asdict(metadata),
                    "audio_processing": asdict(self.stt_provider.audio_processing),
                },
            )
        )

        self.host.start_debug_recording(f"01_stt-{engine}")

        try:
            # Transcribe audio stream
            stt_vad: VoiceCommandSegmenter | None = None
            if (
                self.host.audio_settings.is_vad_enabled
                and self.stt_provider.audio_processing.requires_external_vad
            ):
                stt_vad = VoiceCommandSegmenter(
                    silence_seconds=self.host.audio_settings.silence_seconds
                )

            result = await self.stt_provider.async_process_audio_stream(
                metadata,
                self._speech_to_text_stream(audio_stream=stream, stt_vad=stt_vad),
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
        sample_rate: int = SAMPLE_RATE,
        sample_width: int = SAMPLE_WIDTH,
    ) -> AsyncGenerator[bytes]:
        """Yield audio chunks until VAD detects silence or speech-to-text completes."""
        sent_vad_start = False
        async for chunk in audio_stream:
            self.host.capture_audio(chunk.audio)

            if stt_vad is not None:
                chunk_seconds = (len(chunk.audio) // sample_width) / sample_rate
                if not stt_vad.process(chunk_seconds, chunk.speech_probability):
                    # Silence detected at the end of voice command
                    self.host.process_event(
                        PipelineEvent(
                            PipelineEventType.STT_VAD_END,
                            {"timestamp": chunk.timestamp_ms},
                        )
                    )
                    break

                if stt_vad.in_command and (not sent_vad_start):
                    # Speech detected at start of voice command
                    self.host.process_event(
                        PipelineEvent(
                            PipelineEventType.STT_VAD_START,
                            {"timestamp": chunk.timestamp_ms},
                        )
                    )
                    sent_vad_start = True

            yield chunk.audio

    async def prepare_recognize_intent(self, session: chat_session.ChatSession) -> None:
        """Prepare recognizing an intent."""
        self._conversation_data = async_get_pipeline_conversation_data(
            self.host.hass, session
        )

        if self._conversation_data.continue_conversation_agent is not None:
            agent_info = conversation.async_get_agent_info(
                self.host.hass, self._conversation_data.continue_conversation_agent
            )
            self._conversation_data.continue_conversation_agent = None
            if agent_info is None:
                raise IntentRecognitionError(
                    code="intent-agent-not-found",
                    message=(
                        f"Intent recognition engine"
                        f" {self._conversation_data.continue_conversation_agent}"
                        " asked for follow-up but is no longer found"
                    ),
                )
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

    async def recognize_intent(
        self,
        intent_input: str,
        conversation_id: str,
        conversation_extra_system_prompt: str | None,
    ) -> tuple[str, bool]:
        """Run intent recognition portion of pipeline.

        Returns (speech, all_targets_in_satellite_area).
        """
        if self.intent_agent is None or self._conversation_data is None:
            raise RuntimeError("Recognize intent was not prepared")

        if self.host.pipeline.conversation_language == MATCH_ALL:
            # LLMs support all languages ('*') so use languages from the
            # pipeline for intent fallback.
            #
            # We prioritize the STT and TTS languages because they may be more
            # specific, such as "zh-CN" instead of just "zh". This is necessary
            # for languages whose intents are split out by region when
            # preferring local intent matching.
            input_language = (
                self.host.pipeline.stt_language
                or self.host.pipeline.tts_language
                or self.host.pipeline.language
            )
        else:
            input_language = self.host.pipeline.conversation_language

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.intent_agent.id,
                    "language": input_language,
                    "intent_input": intent_input,
                    "conversation_id": conversation_id,
                    "device_id": self.host.device_id,
                    "satellite_id": self.host.satellite_id,
                    "prefer_local_intents": self.host.pipeline.prefer_local_intents,
                },
            )
        )

        try:
            if self.tts_stream and self.tts_stream.supports_streaming_input:
                tts_input_stream: asyncio.Queue[str | None] | None = asyncio.Queue()
            else:
                tts_input_stream = None
            chat_log_role = None
            delta_character_count = 0

            @callback
            def chat_log_delta_listener(
                chat_log: conversation.ChatLog, delta: dict
            ) -> None:
                """Handle chat log delta."""
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

                nonlocal chat_log_role

                if role := delta.get("role"):
                    chat_log_role = role

                # We are only interested in assistant deltas
                if chat_log_role != "assistant":
                    return

                if content := delta.get("content"):
                    tts_input_stream.put_nowait(content)

                if self._streamed_response_text:
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

                self._streamed_response_text = True

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
                text=intent_input,
                context=self.host.context,
                conversation_id=conversation_id,
                device_id=self.host.device_id,
                satellite_id=self.host.satellite_id,
                language=input_language,
                agent_id=self.intent_agent.id,
                extra_system_prompt=conversation_extra_system_prompt,
            )

            with (
                chat_session.async_get_chat_session(
                    self.host.hass, user_input.conversation_id
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
                if not processed_locally and not self._intent_agent_only:
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
                    )
                    speech = conversation_result.response.speech.get("plain", {}).get(
                        "speech", ""
                    )
                    if tts_input_stream and self._streamed_response_text:
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

        except Exception as src_error:
            _LOGGER.exception("Unexpected error during intent recognition")
            raise IntentRecognitionError(
                code="intent-failed",
                message="Unexpected error during intent recognition",
            ) from src_error

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

    async def prepare_text_to_speech(self) -> None:
        """Prepare text-to-speech."""
        # pipeline.tts_engine can't be None or this function is not called
        engine = cast(str, self.host.pipeline.tts_engine)

        tts_options: dict[str, Any] = {}
        if self.host.pipeline.tts_voice is not None:
            tts_options[tts.ATTR_VOICE] = self.host.pipeline.tts_voice

        if isinstance(self.host.tts_audio_output, dict):
            tts_options.update(self.host.tts_audio_output)
        elif isinstance(self.host.tts_audio_output, str):
            tts_options[tts.ATTR_PREFERRED_FORMAT] = self.host.tts_audio_output
            if self.host.tts_audio_output == "wav":
                # 16 Khz, 16-bit mono
                tts_options[tts.ATTR_PREFERRED_SAMPLE_RATE] = SAMPLE_RATE
                tts_options[tts.ATTR_PREFERRED_SAMPLE_CHANNELS] = SAMPLE_CHANNELS
                tts_options[tts.ATTR_PREFERRED_SAMPLE_BYTES] = SAMPLE_WIDTH

        try:
            self.tts_stream = tts.async_create_stream(
                hass=self.host.hass,
                engine=engine,
                language=self.host.pipeline.tts_language,
                options=tts_options,
            )
        except HomeAssistantError as err:
            raise TextToSpeechError(
                code="tts-not-supported",
                message=(
                    f"Text-to-speech engine {engine} "
                    f"does not support language {self.host.pipeline.tts_language}"
                    f" or options {tts_options}:"
                    f" {err}"
                ),
            ) from err

    async def text_to_speech(
        self, tts_input: str, override_media_path: Path | None = None
    ) -> None:
        """Run text-to-speech portion of pipeline."""
        assert self.tts_stream is not None

        self.host.process_event(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.tts_stream.engine,
                    "language": self.host.pipeline.tts_language,
                    "voice": self.host.pipeline.tts_voice,
                    "tts_input": tts_input,
                    "acknowledge_override": override_media_path is not None,
                },
            )
        )

        if override_media_path:
            self.tts_stream.async_override_result(override_media_path)
        elif not self._streamed_response_text:
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
        self, audio_stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Apply volume transformation only with optional chunking.

        No VAD/audio enhancements are applied.
        """
        timestamp_ms = 0
        async for chunk in audio_stream:
            if self.host.audio_settings.volume_multiplier != 1.0:
                chunk = _multiply_volume(
                    chunk, self.host.audio_settings.volume_multiplier
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
        self, audio_stream: AsyncIterable[bytes]
    ) -> AsyncGenerator[EnhancedAudioChunk]:
        """Split audio into chunks and apply audio enhancements.

        Applies VAD/noise suppression/auto gain/volume
        transformation.
        """
        assert self.audio_enhancer is not None

        timestamp_ms = 0
        async for dirty_samples in audio_stream:
            if self.host.audio_settings.volume_multiplier != 1.0:
                # Static gain
                dirty_samples = _multiply_volume(
                    dirty_samples, self.host.audio_settings.volume_multiplier
                )

            # Split into chunks for audio enhancements/VAD
            for dirty_chunk in chunk_samples(
                dirty_samples, BYTES_PER_CHUNK, self.audio_chunking_buffer
            ):
                yield self.audio_enhancer.enhance_chunk(dirty_chunk, timestamp_ms)
                timestamp_ms += MS_PER_CHUNK

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Run the configured default pipeline stages."""
        current_stage: PipelineStage | None = self.host.start_stage
        stt_audio_buffer: list[EnhancedAudioChunk] = []
        stt_processed_stream: AsyncIterable[EnhancedAudioChunk] | None = None

        if request.stt_stream is not None:
            if self.host.audio_settings.needs_processor:
                # VAD/noise suppression/auto gain/volume
                stt_processed_stream = self.process_enhance_audio(request.stt_stream)
            else:
                # Volume multiplier only
                stt_processed_stream = self.process_volume_only(request.stt_stream)

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
        if current_stage == PipelineStage.STT:
            assert request.stt_metadata is not None
            assert stt_processed_stream is not None

            if request.wake_word_phrase is not None:
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

            intent_input = await self.speech_to_text(
                request.stt_metadata,
                stt_input_stream,
            )
            current_stage = PipelineStage.INTENT

        if self.host.end_stage != PipelineStage.STT:
            tts_input = request.tts_input
            all_targets_in_satellite_area = False

            if current_stage == PipelineStage.INTENT:
                # intent-recognition
                assert intent_input is not None
                (
                    tts_input,
                    all_targets_in_satellite_area,
                ) = await self.recognize_intent(
                    intent_input,
                    request.session.conversation_id,
                    request.conversation_extra_system_prompt,
                )
                if all_targets_in_satellite_area or tts_input.strip():
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
        if self.host.start_stage in (PipelineStage.WAKE_WORD, PipelineStage.STT):
            if self.host.pipeline.stt_engine is None:
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
                raise PipelineRunValidationError(
                    "the pipeline does not support text-to-speech"
                )

        start_stage_index = PIPELINE_STAGE_ORDER.index(self.host.start_stage)
        end_stage_index = PIPELINE_STAGE_ORDER.index(self.host.end_stage)

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
        ):
            assert request.stt_metadata is not None
            prepare_tasks.append(self.prepare_speech_to_text(request.stt_metadata))

        if (
            start_stage_index
            <= PIPELINE_STAGE_ORDER.index(PipelineStage.INTENT)
            <= end_stage_index
        ):
            prepare_tasks.append(self.prepare_recognize_intent(request.session))

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


def _multiply_volume(chunk: bytes, volume_multiplier: float) -> bytes:
    """Multiply 16-bit PCM samples by a constant."""

    def _clamp(val: float) -> float:
        """Clamp to signed 16-bit."""
        return max(-32768, min(32767, val))

    return array.array(
        "h",
        (int(_clamp(value * volume_multiplier)) for value in array.array("h", chunk)),
    ).tobytes()


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
